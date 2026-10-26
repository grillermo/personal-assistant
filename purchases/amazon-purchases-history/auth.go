package main

import (
	"bytes"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"html"
	"log"
	"math/big"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// Sign-in with a one-time code posted to Slack, like rulinky: the code goes to the
// SLACK_OTP_WEBHOOK_URL channel and whoever can read it can sign in.
//
// The session cookie is a signature of a fixed message with a secret kept in
// auth_secret, so it needs no server state and is valid until auth_secret is deleted.
// Browsers cap cookie lifetimes (Chrome: 400 days), so every authenticated
// request sends the cookie again with a fresh lifetime.

const (
	cookieName     = "purchases_session"
	cookieMaxAge   = 400 * 24 * 60 * 60 // the longest lifetime browsers accept
	otpTTL         = 10 * time.Minute
	otpResendAfter = 30 * time.Second
	otpMaxTries    = 5
)

type Auth struct {
	secret  []byte
	webhook string

	mu       sync.Mutex
	code     string
	expires  time.Time
	sentAt   time.Time
	attempts int
}

func newAuth(root string) (*Auth, error) {
	path := filepath.Join(root, "auth_secret")
	data, err := os.ReadFile(path)
	if err != nil || len(bytes.TrimSpace(data)) < 32 {
		raw := make([]byte, 32)
		if _, err := rand.Read(raw); err != nil {
			return nil, err
		}
		data = []byte(hex.EncodeToString(raw))
		if err := os.WriteFile(path, data, 0o600); err != nil {
			return nil, err
		}
	}
	return &Auth{secret: bytes.TrimSpace(data), webhook: os.Getenv("SLACK_OTP_WEBHOOK_URL")}, nil
}

func (a *Auth) token() string {
	mac := hmac.New(sha256.New, a.secret)
	mac.Write([]byte("purchases-session"))
	return base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

func (a *Auth) signedIn(r *http.Request) bool {
	c, err := r.Cookie(cookieName)
	return err == nil && subtle.ConstantTimeCompare([]byte(c.Value), []byte(a.token())) == 1
}

func (a *Auth) setCookie(w http.ResponseWriter, r *http.Request) {
	http.SetCookie(w, &http.Cookie{
		Name: cookieName, Value: a.token(), Path: "/",
		MaxAge: cookieMaxAge, Expires: time.Now().Add(cookieMaxAge * time.Second),
		HttpOnly: true, SameSite: http.SameSiteLaxMode,
		Secure: r.TLS != nil || r.Header.Get("X-Forwarded-Proto") == "https",
	})
}

// Middleware lets /health and the sign-in routes through and sends everyone else to /login.
func (a *Auth) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/health" || strings.HasPrefix(r.URL.Path, "/login") {
			next.ServeHTTP(w, r)
			return
		}
		if !a.signedIn(r) {
			if strings.HasPrefix(r.URL.Path, "/api/") || strings.HasPrefix(r.URL.Path, "/images/") {
				http.Error(w, "unauthorized", http.StatusUnauthorized)
			} else {
				http.Redirect(w, r, "/login", http.StatusSeeOther)
			}
			return
		}
		a.setCookie(w, r)
		next.ServeHTTP(w, r)
	})
}

func (a *Auth) Register(mux *http.ServeMux) {
	mux.HandleFunc("GET /login", func(w http.ResponseWriter, r *http.Request) {
		if a.signedIn(r) {
			http.Redirect(w, r, "/", http.StatusSeeOther)
			return
		}
		a.page(w, "", "")
	})
	mux.HandleFunc("POST /login/send", func(w http.ResponseWriter, r *http.Request) {
		if msg := a.sendCode(); msg != "" {
			a.page(w, msg, "")
			return
		}
		a.page(w, "", "Code sent to Slack.")
	})
	mux.HandleFunc("POST /login/verify", func(w http.ResponseWriter, r *http.Request) {
		if !a.checkCode(r.FormValue("code")) {
			a.page(w, "Invalid or expired code.", "")
			return
		}
		a.setCookie(w, r)
		http.Redirect(w, r, "/", http.StatusSeeOther)
	})
}

// sendCode makes a new code and posts it to Slack; it returns an error message for the page, or "".
func (a *Auth) sendCode() string {
	if a.webhook == "" {
		return "SLACK_OTP_WEBHOOK_URL is not set."
	}
	n, err := rand.Int(rand.Reader, big.NewInt(1_000_000))
	if err != nil {
		return "Could not generate a code."
	}
	a.mu.Lock()
	if time.Since(a.sentAt) < otpResendAfter {
		a.mu.Unlock()
		return "Wait a few seconds before asking for another code."
	}
	a.code, a.expires, a.sentAt, a.attempts = fmt.Sprintf("%06d", n.Int64()), time.Now().Add(otpTTL), time.Now(), 0
	code := a.code
	a.mu.Unlock()

	body, _ := json.Marshal(map[string]string{"text": "Your OTP for purchases " + code})
	resp, err := http.Post(a.webhook, "application/json", bytes.NewReader(body))
	if err != nil || resp.StatusCode >= 300 {
		log.Printf("slack webhook failed: %v", err)
		return "Could not send the code to Slack."
	}
	resp.Body.Close()
	return ""
}

func (a *Auth) checkCode(given string) bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.code == "" || time.Now().After(a.expires) {
		return false
	}
	if a.attempts++; a.attempts > otpMaxTries {
		a.code = ""
		return false
	}
	if subtle.ConstantTimeCompare([]byte(a.code), []byte(strings.TrimSpace(given))) != 1 {
		return false
	}
	a.code = ""
	return true
}

func (a *Auth) page(w http.ResponseWriter, errMsg, info string) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	note := ""
	if errMsg != "" {
		note = `<p class="err">` + html.EscapeString(errMsg) + `</p>`
	} else if info != "" {
		note = `<p>` + html.EscapeString(info) + `</p>`
	}
	fmt.Fprintf(w, `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign in</title>
<style>body{font:16px system-ui;max-width:22rem;margin:20vh auto;padding:0 16px}
input,button{font:inherit;padding:.6rem;width:100%%;box-sizing:border-box;margin:.3rem 0}.err{color:#b00020}</style></head>
<body><h1>Purchases</h1>%s
<form method="post" action="/login/send"><button>Send code to Slack</button></form>
<form method="post" action="/login/verify"><input name="code" inputmode="numeric" autocomplete="one-time-code" placeholder="6-digit code" required><button>Sign in</button></form>
</body></html>`, note)
}
