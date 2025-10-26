#!/usr/bin/env python3
import argparse
import csv
import datetime
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
import requests
from bs4 import BeautifulSoup

def now_ts() -> str:
    return datetime.datetime.utcnow().isoformat()

def http_get(url: str, headers: Optional[Dict[str,str]] = None, timeout: int = 20) -> Tuple[int, str, Dict[str,str]]:
    h = {"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
    if headers:
        h.update(headers)
    resp = requests.get(url, headers=h, timeout=timeout)
    return resp.status_code, resp.text, dict(resp.headers)

def find_urls_in_text(text: str) -> List[str]:
    urls = re.findall(r"https?://[^\s'\"<>]+", text)
    return list(dict.fromkeys(urls))

def search_for_endpoints(html: str, base_url: str) -> List[str]:
    urls = []
    for m in re.finditer(r'["\'](https?://[^"\']*lodgix[^"\']*)["\']', html, flags=re.I):
        u = m.group(1)
        urls.append(u)
    for m in re.finditer(r'["\'](/[^"\']*lodgix[^"\']*)["\']', html, flags=re.I):
        u = m.group(1)
        if base_url.endswith("/"): base = base_url[:-1]
        else: base = base_url
        urls.append(base + u)
    for m in re.finditer(r'["\'](https?://[^"\']*public-api[^"\']*)["\']', html, flags=re.I):
        urls.append(m.group(1))
    for u in find_urls_in_text(html):
        if "/api" in u or "public-api" in u or "lodgix" in u.lower():
            urls.append(u)
    clean = []
    for u in urls:
        if u not in clean:
            clean.append(u)
    return clean

def extract_jsonld(soup: BeautifulSoup) -> List[Dict[str,Any]]:
    out = []
    for tag in soup.find_all("script", {"type":"application/ld+json"}):
        try:
            txt = tag.string or tag.text
            if not txt: continue
            parsed = json.loads(txt.strip())
            if isinstance(parsed, list):
                out.extend(parsed)
            else:
                out.append(parsed)
        except Exception:
            continue
    return out

def extract_inline_json_objects(html: str) -> List[Dict[str,Any]]:
    out = []
    patterns = [
        r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
        r'window\.__DATA__\s*=\s*({.*?});',
        r'var\s+lodgixData\s*=\s*({.*?});',
        r'window\.__Lodgix__\s*=\s*({.*?});',
        r'=\s*({\s*"Listing"[\s\S]*?})\s*;'
    ]
    for p in patterns:
        for m in re.finditer(p, html, flags=re.S):
            txt = m.group(1)
            try:
                parsed = json.loads(txt)
                out.append(parsed)
            except Exception:
                try:
                    parsed = json.loads(re.sub(r'(\w+):', r'"\1":', txt))
                    out.append(parsed)
                except Exception:
                    continue
    js_objs = re.findall(r'(\{(?:[^{}]|(?1))*\})', html, flags=re.S)
    short = []
    for o in js_objs:
        if len(o) < 200: continue
        if '"address"' in o or '"Latitude"' in o or '"latitude"' in o or '"FullAddress"' in o:
            try:
                parsed = json.loads(o)
                short.append(parsed)
            except Exception:
                pass
    out.extend(short)
    return out

def find_address_in_text(text: str) -> Optional[Tuple[str,Optional[float],Optional[float]]]:
    address_patterns = [
        r'FullAddress"\s*:\s*"([^"]+)"',
        r'fullAddress"\s*:\s*"([^"]+)"',
        r'address"\s*:\s*\{[^}]*"streetAddress"\s*:\s*"([^"]+)"',
        r'address"\s*:\s*"([^"]+)"'
    ]
    for p in address_patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            return (m.group(1).strip(), None, None)
    latlon = None
    lat = None
    lon = None
    mlat = re.search(r'Latitude"\s*:\s*([0-9\.\-]+)', text, flags=re.I)
    mlon = re.search(r'Longitude"\s*:\s*([0-9\.\-]+)', text, flags=re.I)
    if mlat and mlon:
        try:
            lat = float(mlat.group(1))
            lon = float(mlon.group(1))
            return (None, lat, lon)
        except Exception:
            pass
    m = re.search(r'geo"\s*:\s*\{\s*"latitude"\s*:\s*([0-9\.\-]+)\s*,\s*"longitude"\s*:\s*([0-9\.\-]+)\s*\}', text, flags=re.I)
    if m:
        try:
            return (None, float(m.group(1)), float(m.group(2)))
        except Exception:
            pass
    return None

def recursive_search_for_keys(obj: Any, keys: List[str]) -> List[Any]:
    found = []
    if isinstance(obj, dict):
        for k,v in obj.items():
            if k.lower() in [kk.lower() for kk in keys]:
                found.append(v)
            found.extend(recursive_search_for_keys(v, keys))
    elif isinstance(obj, list):
        for it in obj:
            found.extend(recursive_search_for_keys(it, keys))
    return found

def normalize_address_candidate(candidate: Any) -> Dict[str,Any]:
    res = {"FullAddress":None,"Latitude":None,"Longitude":None}
    if isinstance(candidate, str):
        res["FullAddress"]=candidate
        return res
    if isinstance(candidate, dict):
        for k in candidate.keys():
            kl = k.lower()
            if "street" in kl or "address" in kl or "fulladdress" in kl or "formatted" in kl or "line1" in kl:
                v = candidate.get(k)
                if isinstance(v, str):
                    if res["FullAddress"]:
                        res["FullAddress"] = res["FullAddress"] + ", " + v
                    else:
                        res["FullAddress"] = v
        if "latitude" in candidate and "longitude" in candidate:
            try:
                res["Latitude"] = float(candidate.get("latitude"))
                res["Longitude"] = float(candidate.get("longitude"))
            except Exception:
                pass
        if "lat" in candidate and "lng" in candidate:
            try:
                res["Latitude"] = float(candidate.get("lat"))
                res["Longitude"] = float(candidate.get("lng"))
            except Exception:
                pass
        if "FullAddress" in candidate:
            res["FullAddress"] = candidate.get("FullAddress")
        if "fullAddress" in candidate:
            res["FullAddress"] = candidate.get("fullAddress")
    return res

def try_call_endpoint(url: str) -> Optional[Dict[str,Any]]:
    try:
        st, txt, headers = http_get(url)
    except Exception:
        return None
    if st >= 400:
        return None
    try:
        return json.loads(txt)
    except Exception:
        ct = headers.get("Content-Type","").lower()
        if "application/json" in ct:
            try:
                return json.loads(txt)
            except Exception:
                return None
        return None

def pick_best_from_json(parsed: Any) -> Optional[Dict[str,Any]]:
    if parsed is None:
        return None
    candidates = []
    candidates.extend(recursive_search_for_keys(parsed, ["FullAddress","fullAddress","address","streetAddress","formattedAddress","location","latlon","geo","latitude","lat"]))
    for c in candidates:
        na = normalize_address_candidate(c)
        if na["FullAddress"] or (na["Latitude"] is not None and na["Longitude"] is not None):
            return na
    return None

def parse_json_ld_objects(objs: List[Dict[str,Any]]) -> Optional[Dict[str,Any]]:
    for o in objs:
        if not o: continue
        if isinstance(o, list):
            for it in o:
                res = pick_best_from_json(it)
                if res: return res
        else:
            res = pick_best_from_json(o)
            if res: return res
    return None

def parse_html_fallback(soup: BeautifulSoup) -> Optional[Dict[str,Any]]:
    textblocks = []
    for t in soup.find_all(text=True):
        textblocks.append(t.strip())
    joined = "\n".join([t for t in textblocks if t])
    addr = None
    m = re.search(r'(\d{1,5}\s+[A-Za-z0-9][^,\\n]{5,},\s*[A-Za-z ]{2,30}\s*\d{5})', joined)
    if m:
        addr = m.group(1).strip()
        return {"FullAddress":addr,"Latitude":None,"Longitude":None}
    meta = {}
    for mtag in soup.find_all("meta"):
        name = mtag.get("name","") or mtag.get("property","")
        content = mtag.get("content","")
        if name and content:
            meta[name.lower()] = content
    for key in ["og:street-address","og:locality","og:region","og:postal-code","og:latitude","og:longitude","geo.position","ICBM"]:
        if key in meta:
            try:
                la = meta.get("og:latitude") or meta.get("latitude") or meta.get("og:lat")
                lo = meta.get("og:longitude") or meta.get("longitude") or meta.get("og:lon")
                if la and lo:
                    return {"FullAddress":None,"Latitude":float(la),"Longitude":float(lo)}
            except Exception:
                pass
    return None

def run_scrape_one(url: str, timeout: int = 20) -> Dict[str,Any]:
    result = {"SourceUrl":url,"Timestamp":now_ts(),"Approach":None,"Success":False,"FullAddress":None,"Latitude":None,"Longitude":None,"Notes":None}
    try:
        st, html, headers = http_get(url, timeout=timeout)
    except Exception as e:
        result["Notes"]=f"fetch-error:{e}"
        return result
    if st >= 400:
        result["Notes"]=f"http-status-{st}"
        return result
    soup = BeautifulSoup(html, "html.parser")
    jsonld = extract_jsonld(soup)
    parsed = parse_json_ld_objects(jsonld)
    if parsed:
        result["Approach"]="json-ld"
        result.update({"FullAddress":parsed.get("FullAddress"),"Latitude":parsed.get("Latitude"),"Longitude":parsed.get("Longitude"),"Success":bool(parsed.get("FullAddress") or (parsed.get("Latitude") is not None and parsed.get("Longitude") is not None))})
        if result["Success"]:
            return result
    inline_objs = extract_inline_json_objects(html)
    parsed2 = parse_json_ld_objects(inline_objs)
    if parsed2:
        result["Approach"]="inline-json"
        result.update({"FullAddress":parsed2.get("FullAddress"),"Latitude":parsed2.get("Latitude"),"Longitude":parsed2.get("Longitude"),"Success":bool(parsed2.get("FullAddress") or (parsed2.get("Latitude") is not None and parsed2.get("Longitude") is not None))})
        if result["Success"]:
            return result
    endpoints = search_for_endpoints(html, url)
    tried = []
    for ep in endpoints:
        if ep in tried: continue
        tried.append(ep)
        api_json = try_call_endpoint(ep)
        if api_json:
            best = pick_best_from_json(api_json)
            if best:
                result["Approach"]="api-crawl"
                result.update({"FullAddress":best.get("FullAddress"),"Latitude":best.get("Latitude"),"Longitude":best.get("Longitude"),"Success":bool(best.get("FullAddress") or (best.get("Latitude") is not None and best.get("Longitude") is not None))})
                result["Notes"]=f"called-endpoint:{ep}"
                if result["Success"]:
                    return result
    findtxt = find_address_in_text(html)
    if findtxt:
        result["Approach"]="regex-text"
        result["FullAddress"]=findtxt[0]
        result["Latitude"]=findtxt[1]
        result["Longitude"]=findtxt[2]
        result["Success"]=bool(findtxt[0] or (findtxt[1] and findtxt[2]))
        if result["Success"]:
            return result
    fallback = parse_html_fallback(soup)
    if fallback:
        result["Approach"]="html-fallback"
        result.update({"FullAddress":fallback.get("FullAddress"),"Latitude":fallback.get("Latitude"),"Longitude":fallback.get("Longitude"),"Success":bool(fallback.get("FullAddress") or (fallback.get("Latitude") is not None and fallback.get("Longitude") is not None))})
        if result["Success"]:
            return result
    result["Notes"]="no-address-found"
    return result

def write_json_output(out: Dict[str,Any], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

def write_csv_log(rows: List[Dict[str,Any]], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    keys = ["SourceUrl","Timestamp","Approach","Success","FullAddress","Latitude","Longitude","Notes"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in keys})

def load_site_list_from_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    return lines

def main():
    p = argparse.ArgumentParser(prog="lodgix_universal_scraper", description="Universal Lodgix scraper - single-file")
    p.add_argument("--url", "-u", help="Single start URL to scrape", default=None)
    p.add_argument("--list", "-l", help="Text file with one URL per line to process", default=None)
    p.add_argument("--outdir", "-o", help="Output directory for results", default="out")
    p.add_argument("--csv", help="Write analysis CSV log (default out/analysis.csv)", default=None)
    p.add_argument("--json", help="Write per-site JSON results into out/json (default)", action="store_true")
    p.add_argument("--timeout", type=int, default=20)
    args = p.parse_args()
    urls = []
    if args.url:
        urls.append(args.url)
    if args.list:
        urls.extend(load_site_list_from_file(args.list))
    if not urls:
        print("No URLs provided. Use --url or --list", file=sys.stderr)
        sys.exit(1)
    os.makedirs(args.outdir, exist_ok=True)
    rows = []
    for u in urls:
        try:
            res = run_scrape_one(u, timeout=args.timeout)
        except Exception as e:
            res = {"SourceUrl":u,"Timestamp":now_ts(),"Approach":None,"Success":False,"FullAddress":None,"Latitude":None,"Longitude":None,"Notes":f"error:{e}"}
        rows.append(res)
        if args.json or True:
            jsdir = os.path.join(args.outdir, "json")
            os.makedirs(jsdir, exist_ok=True)
            fname = re.sub(r'[^0-9A-Za-z\-_\.]', '_', u)[:150] + ".json"
            path = os.path.join(jsdir, fname)
            write_json_output(res, path)
    csvpath = args.csv or os.path.join(args.outdir, "analysis.csv")
    write_csv_log(rows, csvpath)
    print(f"Processed {len(rows)} sites. CSV log: {csvpath}")
    print("Sample results:")
    for r in rows[:5]:
        print(json.dumps(r, ensure_ascii=False))

if __name__ == "__main__":
    main()
