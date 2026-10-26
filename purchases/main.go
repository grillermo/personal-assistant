// Command purchases serves every Amazon, Mercado Libre and AliExpress purchase as a searchable
// Mercado Libre-style catalog.
//
// Data lives in data/<source>/<YYYY-MM-DD>/ and the newest date of each source wins. It is read on
// every request, so rebuilding data/purchases.db (importers/amazon/build.sh), adding a mercadolibre
// meli.json or aliexpress CSVs, or downloading images (importers/amazon/fetch_images.py) shows up
// on the next reload.
package main

import (
	"cmp"
	"database/sql"
	_ "embed"
	"encoding/csv"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"unicode"

	"golang.org/x/text/runes"
	"golang.org/x/text/transform"
	"golang.org/x/text/unicode/norm"
	_ "modernc.org/sqlite"
)

//go:embed web/index.html
var indexHTML []byte

const pageSize = 60

var storeLabels = map[string]string{
	"amazon.com.mx": "Amazon MX",
	"amazon.com":    "Amazon US",
	"amazon.it":     "Amazon IT",
	"mercadolibre":  "Mercado Libre",
	"aliexpress":    "AliExpress",
}

type Purchase struct {
	Store    string  `json:"store"`
	Date     string  `json:"date"`
	Product  string  `json:"product"`
	Brand    string  `json:"brand"`
	Qty      int     `json:"qty"`
	Unit     float64 `json:"unit"`
	Total    float64 `json:"total"`
	Currency string  `json:"currency"`
	Status   string  `json:"status"`
	URL      string  `json:"url"`
	Image    string  `json:"image"`

	haystack string
}

type Store struct {
	Key   string `json:"key"`
	Label string `json:"label"`
	Count int    `json:"count"`
}

// Month is one calendar month of matches with its spend per currency, so a month paged across
// several requests still shows its full total.
type Month struct {
	Key  string             `json:"key"`
	Sums map[string]float64 `json:"sums"`
}

type Result struct {
	Items  []Purchase         `json:"items"`
	Total  int                `json:"total"`
	Stores []Store            `json:"stores"`
	Sums   map[string]float64 `json:"sums"`
	Months []Month            `json:"months"`
}

// monthOf returns "YYYY-MM" for a "YYYY-MM-DD" date.
func monthOf(date string) string {
	return date[:min(7, len(date))]
}

func main() {
	root, err := os.Getwd()
	if err != nil {
		log.Fatal(err)
	}
	port := envOr("PORT", "4031")

	auth, err := newAuth(root)
	if err != nil {
		log.Fatal(err)
	}
	if auth.webhook == "" {
		log.Print("warning: SLACK_OTP_WEBHOOK_URL is not set; nobody can sign in")
	}
	auth.Register(http.DefaultServeMux)

	http.HandleFunc("GET /{$}", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Write(indexHTML)
	})
	http.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, map[string]string{"status": "ok", "port": port})
	})
	http.HandleFunc("GET /api/purchases", func(w http.ResponseWriter, r *http.Request) {
		all, err := loadAll(root)
		if err != nil {
			log.Print(err)
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		writeJSON(w, search(all, r.URL.Query()))
	})
	http.Handle("GET /images/", http.StripPrefix("/images/", http.FileServer(http.Dir(filepath.Join(root, "data", "images")))))

	addr := envOr("HOST", "127.0.0.1") + ":" + port
	log.Printf("purchases listening on http://%s", addr)
	log.Fatal(http.ListenAndServe(addr, logRequests(auth.Middleware(http.DefaultServeMux))))
}

func loadAll(root string) ([]Purchase, error) {
	amazon, err := loadAmazon(filepath.Join(root, "data", "purchases.db"))
	if err != nil {
		return nil, err
	}
	meli, err := loadMeli(filepath.Join(latestImport(root, "mercadolibre"), "meli.json"))
	if err != nil {
		return nil, err
	}
	ali, err := loadAliexpress(latestImport(root, "aliexpress"))
	if err != nil {
		return nil, err
	}
	all := append(append(amazon, meli...), ali...)
	for i := range all {
		p := &all[i]
		p.haystack = fold(p.Product + " " + p.Brand + " " + p.Date + " " + storeLabels[p.Store])
	}
	return all, nil
}

// latestImport returns the newest data/<source>/<date> directory, or a path that does not exist
// when the source has no imports yet.
func latestImport(root, source string) string {
	dir := filepath.Join(root, "data", source)
	entries, _ := os.ReadDir(dir)
	latest := ""
	for _, e := range entries {
		if e.IsDir() && e.Name() > latest {
			latest = e.Name()
		}
	}
	return filepath.Join(dir, cmp.Or(latest, "none"))
}

func loadAmazon(path string) ([]Purchase, error) {
	db, err := sql.Open("sqlite", "file:"+path+"?mode=ro")
	if err != nil {
		return nil, err
	}
	defer db.Close()

	rows, err := db.Query(`select site, date, product, department, qty, unit_price, total, currency, status, url, asin from purchases`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var out []Purchase
	for rows.Next() {
		var site, date, product, dept, currency, status, url, asin sql.NullString
		var qty sql.NullInt64
		var unit, total sql.NullFloat64
		if err := rows.Scan(&site, &date, &product, &dept, &qty, &unit, &total, &currency, &status, &url, &asin); err != nil {
			return nil, err
		}
		brand := dept.String
		if brand == "Not Available" {
			brand = ""
		}
		out = append(out, Purchase{
			Store: strings.ToLower(site.String), Date: date.String, Product: product.String, Brand: brand,
			Qty: max(int(qty.Int64), 1), Unit: unit.Float64, Total: total.Float64,
			Currency: currency.String, Status: status.String, URL: url.String,
			Image: "/images/" + asin.String + ".jpg",
		})
	}
	return out, rows.Err()
}

// meli.json holds Mercado Libre purchases, which have no official export:
// [{date, product, seller, qty, unit_price, total, currency, status, url, image}]
func loadMeli(path string) ([]Purchase, error) {
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	} else if err != nil {
		return nil, err
	}
	var raw []struct {
		Date      string  `json:"date"`
		Product   string  `json:"product"`
		Seller    string  `json:"seller"`
		Qty       int     `json:"qty"`
		UnitPrice float64 `json:"unit_price"`
		Total     float64 `json:"total"`
		Currency  string  `json:"currency"`
		Status    string  `json:"status"`
		URL       string  `json:"url"`
		Image     string  `json:"image"`
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, err
	}
	out := make([]Purchase, 0, len(raw))
	for _, m := range raw {
		out = append(out, Purchase{
			Store: "mercadolibre", Date: m.Date, Product: m.Product, Brand: m.Seller,
			Qty: max(m.Qty, 1), Unit: m.UnitPrice, Total: m.Total,
			Currency: cmp.Or(m.Currency, "MXN"), Status: m.Status, URL: m.URL, Image: m.Image,
		})
	}
	return out, nil
}

// data/aliexpress/<date>/*.csv are AliExpress order exports, one row per item, with
// Spanish dates ("27 sep, 2026") and prices like "MX$1,236.99".
func loadAliexpress(dir string) ([]Purchase, error) {
	files, err := filepath.Glob(filepath.Join(dir, "*.csv"))
	if err != nil {
		return nil, err
	}
	var out []Purchase
	for _, f := range files {
		rows, err := readCSV(f)
		if err != nil {
			return nil, err
		}
		items := map[string]int{}
		for _, r := range rows {
			items[r["Order ID"]]++
		}
		for _, r := range rows {
			qty, _ := strconv.ParseFloat(r["Item Qty"], 64)
			unit := parseMoney(r["Item Price"])
			// The order total includes shipping and taxes, but only fits an order with one item.
			total := parseMoney(r["Total Price Original"])
			if items[r["Order ID"]] > 1 {
				total = unit * max(qty, 1)
			}
			out = append(out, Purchase{
				Store: "aliexpress", Date: aliDate(r["Order Date"]), Product: r["Item Title"], Brand: r["Store Name"],
				Qty: max(int(qty), 1), Unit: unit, Total: total,
				Currency: cmp.Or(r["Original Currency"], "MXN"), Status: r["Status"], URL: r["Product Link"],
				Image: "/images/ali-" + r["Product ID"] + ".jpg",
			})
		}
	}
	return out, nil
}

func readCSV(path string) ([]map[string]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	records, err := csv.NewReader(f).ReadAll()
	if err != nil || len(records) == 0 {
		return nil, err
	}
	header := records[0]
	var out []map[string]string
	for _, rec := range records[1:] {
		row := map[string]string{}
		for i, h := range header {
			if i < len(rec) {
				row[h] = rec[i]
			}
		}
		out = append(out, row)
	}
	return out, nil
}

var spanishMonths = map[string]string{
	"ene": "01", "feb": "02", "mar": "03", "abr": "04", "may": "05", "jun": "06",
	"jul": "07", "ago": "08", "sep": "09", "oct": "10", "nov": "11", "dic": "12",
}

// aliDate turns "2 dic, 2025" into "2025-12-02"; anything else is returned as is.
func aliDate(s string) string {
	f := strings.Fields(strings.ReplaceAll(s, ",", ""))
	if len(f) != 3 || len(f[0]) > 2 {
		return s
	}
	month, ok := spanishMonths[strings.ToLower(f[1])[:min(3, len(f[1]))]]
	if !ok {
		return s
	}
	return f[2] + "-" + month + "-" + strings.Repeat("0", 2-len(f[0])) + f[0]
}

// parseMoney reads "MX$1,236.99" or "205.62".
func parseMoney(s string) float64 {
	v, _ := strconv.ParseFloat(strings.Map(func(r rune) rune {
		if unicode.IsDigit(r) || r == '.' {
			return r
		}
		return -1
	}, s), 64)
	return v
}

// search filters by every word of q (accent and case insensitive) and by store,
// then sorts and returns one page. Store counts and currency sums cover all matches.
func search(all []Purchase, params map[string][]string) Result {
	get := func(k string) string {
		if v := params[k]; len(v) > 0 {
			return v[0]
		}
		return ""
	}
	words := strings.Fields(fold(get("q")))
	store := get("store")
	offset, _ := strconv.Atoi(get("offset"))

	counts := map[string]int{}
	var matches []Purchase
	for _, p := range all {
		if !containsAll(p.haystack, words) {
			continue
		}
		counts[p.Store]++
		if store == "" || store == "all" || store == p.Store {
			matches = append(matches, p)
		}
	}

	less := map[string]func(a, b Purchase) bool{
		"old":  func(a, b Purchase) bool { return a.Date < b.Date },
		"high": func(a, b Purchase) bool { return a.Total > b.Total },
		"low":  func(a, b Purchase) bool { return a.Total < b.Total },
	}[get("sort")]
	if less == nil {
		less = func(a, b Purchase) bool { return a.Date > b.Date }
	}
	// Months stay in date order whatever the sort, because the page groups purchases by month;
	// the chosen sort only orders the purchases inside each month.
	oldestFirst := get("sort") == "old"
	sort.SliceStable(matches, func(i, j int) bool {
		a, b := matches[i], matches[j]
		if ma, mb := monthOf(a.Date), monthOf(b.Date); ma != mb {
			return (ma < mb) == oldestFirst
		}
		return less(a, b)
	})

	res := Result{Total: len(matches), Sums: map[string]float64{}, Items: []Purchase{}, Months: []Month{}}
	for _, p := range matches {
		res.Sums[p.Currency] += p.Total
		key := monthOf(p.Date)
		if n := len(res.Months); n == 0 || res.Months[n-1].Key != key {
			res.Months = append(res.Months, Month{Key: key, Sums: map[string]float64{}})
		}
		res.Months[len(res.Months)-1].Sums[p.Currency] += p.Total
	}
	if offset < len(matches) {
		res.Items = matches[offset:min(offset+pageSize, len(matches))]
	}
	for key, n := range counts {
		res.Stores = append(res.Stores, Store{Key: key, Label: cmp.Or(storeLabels[key], key), Count: n})
	}
	sort.Slice(res.Stores, func(i, j int) bool { return res.Stores[i].Count > res.Stores[j].Count })
	return res
}

func containsAll(haystack string, words []string) bool {
	for _, w := range words {
		if !strings.Contains(haystack, w) {
			return false
		}
	}
	return true
}

var stripMarks = transform.Chain(norm.NFD, runes.Remove(runes.In(unicode.Mn)), norm.NFC)

func fold(s string) string {
	out, _, err := transform.String(stripMarks, s)
	if err != nil {
		out = s
	}
	return strings.ToLower(out)
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(v); err != nil {
		log.Print(err)
	}
}

func logRequests(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasPrefix(r.URL.Path, "/images/") && r.URL.Path != "/health" {
			log.Printf("%s %s", r.Method, r.URL.RequestURI())
		}
		next.ServeHTTP(w, r)
	})
}

func envOr(key, fallback string) string {
	return cmp.Or(os.Getenv(key), fallback)
}
