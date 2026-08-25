#!/usr/bin/env python3
"""
Macroterritórios de Rio Branco v2 — Central Samir 2026

Melhoria principal:
- Usa as coordenadas já existentes no formulário e/ou na aba privada
  `Mapa_Coordenadas`, criada pelo App de Rua.
- Só usa o nome do bairro como fallback quando não há coordenada.
- Não exige nenhuma nova pergunta no Forms.
- Não exporta nome, telefone, endereço, CEP ou coordenadas individuais.

A base de apoiadores continua sendo sinal de organização residencial,
não pesquisa eleitoral.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import math
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import gspread
import numpy as np
import pandas as pd
from google.oauth2.service_account import Credentials

HISTORICO_PATH = Path(os.getenv("HISTORICO_PATH", "dados.csv"))
ELEITORADO_PATH = Path(os.getenv("ELEITORADO_2026_PATH", "eleitorado_2026_ac.csv"))
OUTPUT_PATH = Path(os.getenv("MACRO_OUTPUT", "macroterritorios_rio_branco_v2.json"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
WORKSHEET_ENV = os.getenv("SUPPORTER_WORKSHEET", "").strip()
CACHE_SHEET = os.getenv("MAP_CACHE_WORKSHEET", "Mapa_Coordenadas")
MIN_CELL = int(os.getenv("SUPPORTER_MIN_CELL", "10"))
K_URBANO = int(os.getenv("MACRO_K_URBANO", "6"))
ACRE_TZ = timezone(timedelta(hours=-5))


def norm(v: Any) -> str:
    s = "" if v is None else str(v).strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", " ", s.upper())
    return re.sub(r"\s+", " ", s).strip()


def norm_map(v: Any) -> str:
    s = unicodedata.normalize("NFKD", str(v or ""))
    s = s.encode("ascii", errors="ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def service_account_from_env() -> dict[str, Any]:
    raw = os.getenv("GCP_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        raise RuntimeError("Defina GCP_SERVICE_ACCOUNT_JSON nos Secrets.")
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        import tomllib
        obj = tomllib.loads(raw)
        obj = obj.get("gcp_service_account", obj)
    if not isinstance(obj, dict):
        raise RuntimeError("Credencial inválida.")
    pk = obj.get("private_key")
    if isinstance(pk, str) and "\\n" in pk:
        obj["private_key"] = pk.replace("\\n", "\n")
    return obj


def achar_coluna(headers, aliases, contem=None):
    mapa = {norm(h): h for h in headers}
    for a in aliases:
        if norm(a) in mapa:
            return mapa[norm(a)]
    termos = [norm(x) for x in (contem or [])]
    for h in headers:
        nh = norm(h)
        if termos and all(t in nh for t in termos):
            return h
    return None


def achar_coluna_mapa(headers, opcoes):
    mapa = {norm_map(h): h for h in headers}
    for opcao in opcoes:
        n = norm_map(opcao)
        if n in mapa:
            return mapa[n]
    for nh, original in mapa.items():
        if any(norm_map(op) in nh for op in opcoes):
            return original
    return None


def texto(row, col, padrao=""):
    if not col:
        return padrao
    v = row.get(col, padrao)
    if v is None:
        return padrao
    s = str(v).strip()
    return padrao if s.lower() in ("", "nan", "none") else s


def num(v):
    try:
        return float(str(v).strip().replace(",", "."))
    except Exception:
        return None


def coord_acre(lat, lon):
    return (
        lat is not None and lon is not None
        and -12.0 <= lat <= -6.5
        and -74.5 <= lon <= -66.0
    )


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2-lat1)
    dl = math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(math.sqrt(a))


def escolher_aba(book):
    candidatos = [x for x in [
        WORKSHEET_ENV,
        "Samir Bestene - Apoiadores (Respostas)",
        "Samir Bestene – Apoiadores (Respostas)",
        "Form_Responses",
        "Form Responses",
    ] if x]
    mapa = {norm(ws.title): ws for ws in book.worksheets()}
    for nome in candidatos:
        if norm(nome) in mapa:
            return mapa[norm(nome)]
    raise RuntimeError(f"Aba de apoiadores não encontrada. Abas: {[w.title for w in book.worksheets()]}")


def abrir_google():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(service_account_from_env(), scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)


def carregar_cache(book):
    try:
        ws = book.worksheet(CACHE_SHEET)
    except Exception:
        return {}
    rows = ws.get_all_records(default_blank="")
    out = {}
    for r in rows:
        chave = str(r.get("CHAVE_ENDERECO", "")).strip()
        lat = num(r.get("LATITUDE"))
        lon = num(r.get("LONGITUDE"))
        if chave and coord_acre(lat, lon):
            out[chave] = (lat, lon, str(r.get("PRECISAO", "")).strip(), str(r.get("FONTE", "")).strip())
    return out


def montar_endereco(row, col_endereco, col_rua, col_bairro, col_cep, col_mun):
    municipio = texto(row, col_mun, "Rio Branco")
    bairro = texto(row, col_bairro)
    cep = re.sub(r"\D", "", texto(row, col_cep))
    completo = texto(row, col_endereco)

    if completo:
        partes = [completo]
        if norm_map(municipio) not in norm_map(completo):
            partes.append(municipio)
        if cep and cep not in re.sub(r"\D", "", completo):
            partes.append(cep)
        partes.extend(["Acre", "Brasil"])
    else:
        rua = texto(row, col_rua)
        partes = [rua, bairro, municipio, "Acre", cep, "Brasil"]
    return ", ".join(x for x in partes if x).strip(" ,")


def coordenada_da_linha(row, col_lat, col_lon, col_coord):
    lat = num(row.get(col_lat)) if col_lat else None
    lon = num(row.get(col_lon)) if col_lon else None
    if not coord_acre(lat, lon) and col_coord:
        s = texto(row, col_coord)
        nums = re.findall(r"-?\d{1,3}(?:[\.,]\d+)", s)
        if len(nums) >= 2:
            lat, lon = num(nums[0]), num(nums[1])
    return (lat, lon) if coord_acre(lat, lon) else (None, None)


def carregar_apoiadores():
    book = abrir_google()
    cache = carregar_cache(book)
    ws = escolher_aba(book)
    rows = ws.get_all_records(default_blank="")
    if not rows:
        raise RuntimeError("Aba de apoiadores vazia.")

    headers = list(rows[0].keys())
    col_mun = (
        achar_coluna(headers, ["Município", "Municipio", "Cidade"])
        or achar_coluna(headers, [], contem=["MUNICIP"])
        or achar_coluna(headers, [], contem=["CIDADE"])
    )
    col_bairro = achar_coluna(headers, ["Bairro"]) or achar_coluna(headers, [], contem=["BAIRRO"])
    col_endereco = achar_coluna_mapa(headers, ["Endereço Completo", "Endereco Completo"])
    col_rua = achar_coluna_mapa(headers, ["Rua e Número", "Rua e Numero", "Logradouro"])
    col_cep = achar_coluna_mapa(headers, ["CEP"])
    col_lat = achar_coluna_mapa(headers, ["Latitude", "Lat"])
    col_lon = achar_coluna_mapa(headers, ["Longitude", "Lng", "Lon"])
    col_coord = achar_coluna_mapa(headers, ["Coordenadas", "Localização", "Localizacao", "LatLong"])

    if not col_mun or not col_bairro:
        raise RuntimeError("Não foi possível localizar município e bairro.")

    itens = []
    for r in rows:
        if norm(r.get(col_mun, "")) != "RIO BRANCO":
            continue

        bairro = norm(r.get(col_bairro, "")) or "BAIRRO NAO INFORMADO"
        lat, lon = coordenada_da_linha(r, col_lat, col_lon, col_coord)
        fonte = "COORDENADA_FORM"

        if lat is None:
            endereco = montar_endereco(r, col_endereco, col_rua, col_bairro, col_cep, col_mun)
            if endereco:
                chave = hashlib.sha256(norm_map(endereco).encode("utf-8")).hexdigest()[:24]
                cached = cache.get(chave)
                if cached:
                    lat, lon = cached[0], cached[1]
                    fonte = "CACHE_MAPA"
                else:
                    fonte = "SEM_COORDENADA"
            else:
                fonte = "SEM_ENDERECO"

        # Só aceitamos coordenadas plausíveis de Rio Branco para esta etapa.
        if lat is not None and haversine_km(lat, lon, -9.9749, -67.8243) > 65:
            lat, lon = None, None
            fonte = "COORDENADA_FORA_RB"

        itens.append({
            "BAIRRO": bairro,
            "LAT": lat,
            "LON": lon,
            "FONTE_COORD": fonte,
        })

    meta = {
        "aba": ws.title,
        "total_rio_branco": len(itens),
        "cache_coordenadas": len(cache),
        "colunas": {
            "bairro": col_bairro,
            "municipio": col_mun,
            "endereco_completo": col_endereco or "",
            "rua": col_rua or "",
            "cep": col_cep or "",
            "lat": col_lat or "",
            "lon": col_lon or "",
            "coordenadas": col_coord or "",
        }
    }
    return pd.DataFrame(itens), meta


def carregar_bases():
    hist = pd.read_csv(HISTORICO_PATH, encoding="utf-8-sig")
    ele = pd.read_csv(ELEITORADO_PATH, dtype={"CD_MUNICIPIO":"string"})
    ele = ele[ele["NM_MUNICIPIO"].map(norm).eq("RIO BRANCO")].copy()
    hist = hist[hist["NM_MUNICIPIO"].map(norm).eq("RIO BRANCO")].copy()

    for df in [ele, hist]:
        df["NR_ZONA"] = pd.to_numeric(df["NR_ZONA"], errors="coerce").astype("Int64")
        df["NR_SECAO"] = pd.to_numeric(df["NR_SECAO"], errors="coerce").astype("Int64")

    ele["QT_ELEITOR_SECAO"] = pd.to_numeric(ele["QT_ELEITOR_SECAO"], errors="coerce").fillna(0)
    ele["LATITUDE"] = pd.to_numeric(ele["LATITUDE"], errors="coerce")
    ele["LONGITUDE"] = pd.to_numeric(ele["LONGITUDE"], errors="coerce")
    ele["BAIRRO_KEY"] = ele["NM_BAIRRO"].fillna("").map(norm)
    hist["QT_VOTOS_SAMIR"] = pd.to_numeric(hist["QT_VOTOS_SAMIR"], errors="coerce").fillna(0)
    return hist, ele


def centroides_bairro(ele):
    e = ele.dropna(subset=["LATITUDE","LONGITUDE"]).copy()

    def agg(g):
        w = g["QT_ELEITOR_SECAO"].to_numpy(float)
        if w.sum() <= 0:
            w = np.ones(len(g))
        return pd.Series({
            "ELEITORES": float(g["QT_ELEITOR_SECAO"].sum()),
            "LAT": float(np.average(g["LATITUDE"], weights=w)),
            "LON": float(np.average(g["LONGITUDE"], weights=w)),
            "NM_BAIRRO": str(g["NM_BAIRRO"].dropna().iloc[0]) if g["NM_BAIRRO"].notna().any() else "",
        })

    return e.groupby("BAIRRO_KEY").apply(agg, include_groups=False).reset_index()


def weighted_kmeans(points, weights, k, max_iter=100):
    n = len(points)
    k = max(1, min(k, n))
    first = int(np.argmax(weights))
    centers = [points[first]]
    for _ in range(1, k):
        d2 = np.min(np.stack([np.sum((points-c)**2, axis=1) for c in centers], axis=1), axis=1)
        idx = int(np.argmax(d2*np.maximum(weights,1.0)))
        centers.append(points[idx])
    centers = np.array(centers, float)
    labels = np.zeros(n, int)
    for it in range(max_iter):
        dist = np.stack([np.sum((points-c)**2, axis=1) for c in centers], axis=1)
        new = np.argmin(dist, axis=1)
        if it > 0 and np.array_equal(new, labels):
            break
        labels = new
        for j in range(k):
            mask = labels == j
            if mask.any():
                centers[j] = np.average(points[mask], axis=0, weights=weights[mask])
    return labels


def construir_macros(ele):
    b = centroides_bairro(ele)
    rural = b["BAIRRO_KEY"].str.contains("ZONA RURAL", na=False)
    u = b[~rural].copy()
    r = b[rural].copy()

    lat0 = math.radians(float(u["LAT"].median()))
    pts = np.column_stack([u["LON"].to_numpy()*math.cos(lat0), u["LAT"].to_numpy()])
    weights = u["ELEITORES"].to_numpy()
    u["CLUSTER"] = weighted_kmeans(pts, weights, K_URBANO)

    info = []
    for c in sorted(u["CLUSTER"].unique()):
        g = u[u["CLUSTER"].eq(c)]
        info.append((c, float(g["LAT"].mean()), float(g["LON"].mean())))
    order = sorted(info, key=lambda x:(-x[1],x[2]))
    remap = {old:i+1 for i,(old,_,_) in enumerate(order)}
    u["MACRO_ID"] = u["CLUSTER"].map(lambda x:f"RB-{remap[x]:02d}")

    macros = []
    bairro_macro = {}
    for mid,g in u.groupby("MACRO_ID"):
        top = g.sort_values("ELEITORES", ascending=False).head(3)["NM_BAIRRO"].astype(str).tolist()
        lat = float(np.average(g["LAT"], weights=g["ELEITORES"]))
        lon = float(np.average(g["LON"], weights=g["ELEITORES"]))
        macros.append({
            "macro_id":mid,
            "nome":f"Macroterritório {mid.split('-')[1]} — {' / '.join(top)}",
            "tipo":"URBANO",
            "eleitores_2026":int(g["ELEITORES"].sum()),
            "bairros_referencia":top,
            "bairros":sorted(g["BAIRRO_KEY"].tolist()),
            "lat":lat,"lon":lon,
        })
        for bkey in g["BAIRRO_KEY"]:
            bairro_macro[bkey]=mid

    if not r.empty:
        mid="RB-RURAL"
        macros.append({
            "macro_id":mid,
            "nome":"Macroterritório Rural",
            "tipo":"RURAL",
            "eleitores_2026":int(r["ELEITORES"].sum()),
            "bairros_referencia":r.sort_values("ELEITORES",ascending=False).head(3)["NM_BAIRRO"].astype(str).tolist(),
            "bairros":sorted(r["BAIRRO_KEY"].tolist()),
            "lat":float(np.average(r["LAT"],weights=r["ELEITORES"])),
            "lon":float(np.average(r["LON"],weights=r["ELEITORES"])),
        })
        for bkey in r["BAIRRO_KEY"]:
            bairro_macro[bkey]=mid

    return macros,bairro_macro


ALIASES = {
    "UNIVERSITARIO":"CONJUNTO UNIVERSITARIO",
    "CONJ UNIVERSITARIO":"CONJUNTO UNIVERSITARIO",
}


def match_bairro(nome, oficiais):
    n=ALIASES.get(nome,nome)
    if n in oficiais:
        return n
    scores=sorted([(difflib.SequenceMatcher(None,n,o).ratio(),o) for o in oficiais], reverse=True)
    if not scores:
        return None
    best,b= scores[0]
    second=scores[1][0] if len(scores)>1 else 0
    if best>=0.94 and best-second>=0.05:
        return b
    return None


def macro_mais_proximo(lat,lon,macros):
    urbanos=[m for m in macros if m["tipo"]=="URBANO"]
    d=[(haversine_km(lat,lon,m["lat"],m["lon"]),m["macro_id"]) for m in urbanos]
    dist,mid=min(d,key=lambda x:x[0])
    return mid,dist


def mapear_apoiadores(apoiadores, macros, bairro_macro):
    oficiais=sorted(bairro_macro.keys())
    counts=Counter()
    fontes=Counter()
    nao=Counter()

    for _,r in apoiadores.iterrows():
        bairro=r["BAIRRO"]
        lat,lon=r["LAT"],r["LON"]

        if "ZONA RURAL" in bairro:
            counts["RB-RURAL"] += 1
            fontes["BAIRRO_RURAL"] += 1
            continue

        if pd.notna(lat) and pd.notna(lon):
            mid,dist=macro_mais_proximo(float(lat),float(lon),macros)
            # Aceitamos localização residencial urbana até 25 km do centro do macro mais próximo.
            if dist <= 25:
                counts[mid]+=1
                fontes["COORDENADA"]+=1
                continue

        b=match_bairro(bairro,oficiais)
        if b and bairro_macro.get(b):
            counts[bairro_macro[b]]+=1
            fontes["BAIRRO_SEGURO"]+=1
        else:
            nao[bairro]+=1
            fontes["NAO_MAPEADO"]+=1

    return counts,fontes,nao


def historico_macro(hist,ele,bairro_macro):
    sec=ele[["NR_ZONA","NR_SECAO","BAIRRO_KEY"]].drop_duplicates(["NR_ZONA","NR_SECAO"])
    sec["MACRO_ID"]=sec["BAIRRO_KEY"].map(bairro_macro)
    h=hist[hist["ANO_ELEICAO"].isin([2020,2022,2024])].merge(
        sec[["NR_ZONA","NR_SECAO","MACRO_ID"]],
        on=["NR_ZONA","NR_SECAO"],how="left",validate="many_to_one"
    )
    cov=[]
    for ano,g in h.groupby("ANO_ELEICAO"):
        vt=float(g["QT_VOTOS_SAMIR"].sum())
        vm=float(g.loc[g["MACRO_ID"].notna(),"QT_VOTOS_SAMIR"].sum())
        cov.append({"ano":int(ano),"cobertura_pct":round(vm/vt*100 if vt else 0,1)})
    hm=h[h["MACRO_ID"].notna()].groupby(["ANO_ELEICAO","MACRO_ID"],as_index=False).agg(VOTOS=("QT_VOTOS_SAMIR","sum"))
    return hm,cov


def classe(h,o,n,confidence):
    if confidence=="BAIXA":
        return "EXPLORATÓRIO"
    if h is None or o is None or n<MIN_CELL:
        return "SINAL INSUFICIENTE"
    if h>=1 and o>=1:return "CONSOLIDAR"
    if h>=1 and o<1:return "RECUPERAR ORGANIZAÇÃO"
    if h<1 and o>=1:return "SINAL DE EXPANSÃO"
    return "DIAGNOSTICAR"


def main():
    hist,ele=carregar_bases()
    apoiadores,meta_ap=carregar_apoiadores()
    macros,bairro_macro=construir_macros(ele)
    ap_counts,fontes,nao=mapear_apoiadores(apoiadores,macros,bairro_macro)
    hm,cob_hist=historico_macro(hist,ele,bairro_macro)

    mapped=sum(ap_counts.values())
    total=len(apoiadores)
    coverage=round(mapped/total*100 if total else 0,1)
    confidence="ALTA" if coverage>=85 else ("MÉDIA" if coverage>=70 else "BAIXA")

    md=pd.DataFrame(macros)
    total_ele=float(md["eleitores_2026"].sum())
    hist_idx=defaultdict(list)
    for ano,g in hm.groupby("ANO_ELEICAO"):
        total_v=float(g["VOTOS"].sum())
        for _,r in g.iterrows():
            em=float(md.loc[md["macro_id"].eq(r["MACRO_ID"]),"eleitores_2026"].iloc[0])
            taxa=(float(r["VOTOS"])/em) if em else np.nan
            ref=(total_v/total_ele) if total_ele else np.nan
            if ref and pd.notna(taxa):
                hist_idx[r["MACRO_ID"]].append(taxa/ref)

    out=[]
    for m in macros:
        mid=m["macro_id"]
        n=int(ap_counts.get(mid,0))
        h=float(np.median(hist_idx[mid])) if hist_idx[mid] else None
        o=None
        if mapped>0 and m["eleitores_2026"]>0:
            o=(n/mapped)/(m["eleitores_2026"]/total_ele)
        out.append({
            **m,
            "lat":round(m["lat"],6),"lon":round(m["lon"],6),
            "apoiadores_mapeados":n if n>=MIN_CELL else f"<{MIN_CELL}",
            "indice_historico":round(h,2) if h is not None else None,
            "indice_organizacao":round(o,2) if o is not None and n>=MIN_CELL else None,
            "classificacao":classe(h,o,n,confidence),
        })

    relevantes=[
        {"bairro_declarado":b.title(),"apoiadores":n}
        for b,n in nao.most_common()
        if n>=MIN_CELL
    ]

    payload={
        "meta":{
            "gerado_em":datetime.now(ACRE_TZ).isoformat(timespec="seconds"),
            "versao":"2.0",
            "metodo":"Coordenadas residenciais já existentes/cache do App de Rua; fallback conservador por bairro; macroterritórios eleitorais por coordenadas dos locais de votação.",
            "privacidade":"Sem PII; nenhuma coordenada individual é exportada.",
        },
        "qualidade":{
            "apoiadores_rio_branco":total,
            "apoiadores_mapeados_com_seguranca":mapped,
            "cobertura_apoiadores_pct":coverage,
            "confianca_cruzamento_residencial_eleitoral":confidence,
            "fontes_mapeamento":dict(fontes),
            "cache_mapa_registros":meta_ap["cache_coordenadas"],
            "colunas_localizacao_detectadas":meta_ap["colunas"],
            "cobertura_historico":cob_hist,
            "alerta":"A comparação é territorial agregada. Organização residencial não equivale a intenção de voto nem garante local de votação.",
        },
        "resumo":dict(Counter(x["classificacao"] for x in out)),
        "macroterritorios":out,
        "bairros_residenciais_nao_mapeados_relevantes":relevantes,
    }

    OUTPUT_PATH.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
        "ok":True,
        "saida":str(OUTPUT_PATH),
        "apoiadores_rb":total,
        "mapeados":mapped,
        "cobertura_pct":coverage,
        "confianca":confidence,
        "fontes":dict(fontes),
    },ensure_ascii=False))


if __name__=="__main__":
    main()
