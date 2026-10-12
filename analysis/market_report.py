"""
Relatório mensal do Raio-X do mercado: só números agregados, prontos para publicar.

Nunca lista vagas individuais (títulos, empresas, links) — ver cuidados na
anotação do projeto: os termos do Seek restringem coleta automatizada, então o
que vai a público são contagens, percentuais e faixas.

Uso: python main.py --market-report [YYYY-MM]   (padrão: mês corrente)
"""

import re
from calendar import monthrange
from datetime import date
from pathlib import Path

import pandas as pd
from rich import box
from rich.console import Console
from rich.table import Table

from config.config import MARKET_CONFIG
from db.database import fetch_market_counts, fetch_market_listings, fetch_market_runs

console    = Console()
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "market"

_TERM_LABELS = {
    "sponsorship":    'citam "sponsorship"',
    "482":            'citam "482"',
    "working_rights": 'citam "working rights"',
    "citizen":        'citam "citizen"',
}


def _month_bounds(month: str) -> tuple[str, str]:
    y, m = map(int, month.split("-"))
    return f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{monthrange(y, m)[1]:02d}"


def _prev_month(month: str) -> str:
    y, m = map(int, month.split("-"))
    return f"{y - 1}-12" if m == 1 else f"{y:04d}-{m - 1:02d}"


def _norm(text) -> str:
    text = text if isinstance(text, str) else ""   # empresa oculta vem como NaN
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """Anúncio repetido = mesmo título + empresa na mesma cidade com IDs diferentes."""
    if df.empty:
        return df
    key = df["title"].map(_norm) + "|" + df["company"].map(_norm) + "|" + df["city"]
    return df.assign(_key=key).sort_values("first_seen").drop_duplicates("_key")


def _avg_counts(month: str) -> pd.DataFrame:
    """Média diária de cada contagem no mês → colunas (category, city, term, avg, days)."""
    start, end = _month_bounds(month)
    df = pd.DataFrame(fetch_market_counts(start, end))
    if df.empty:
        return df
    return (df.groupby(["category", "city", "term"])["total"]
              .agg(avg="mean", days="nunique").reset_index())


def _money(v: float | None) -> str:
    return "—" if v is None or pd.isna(v) else f"${v / 1000:,.0f}k"


def _pct(part: float | None, whole: float | None) -> str:
    if part is None or not whole or pd.isna(part):
        return "—"
    return f"{100 * part / whole:.1f}%"


def build_market_report(month: str | None = None) -> Path | None:
    month = month or date.today().strftime("%Y-%m")
    start, end = _month_bounds(month)

    cur  = _avg_counts(month)
    prev = _avg_counts(_prev_month(month))
    if cur.empty:
        console.print(f"[yellow]Sem retratos válidos em {month}. Rode: python main.py --market[/yellow]")
        return None

    listings = pd.DataFrame(fetch_market_listings(start, end))
    if not listings.empty:
        listings["listed_month"] = listings["listed_at"].fillna("").str[:7]
        listings["salary_mid"]   = listings[["salary_annual_min", "salary_annual_max"]].mean(axis=1)

    days_covered = int(cur["days"].max())
    skipped      = [r for r in fetch_market_runs(start, end) if r["status"] != "ok"]
    terms        = list(MARKET_CONFIG.get("mention_terms", {}))

    lines = [
        f"# Raio-X do mercado australiano — {month}",
        "",
        f"Fonte: Seek (subclassificações oficiais). Média de {days_covered} retrato(s) diário(s) no mês"
        + (f"; {len(skipped)} descartado(s) por coleta incompleta ou suspeita." if skipped else "."),
        "",
    ]

    tbl = Table(title=f"Raio-X {month} (% = anúncios que citam o termo)", box=box.SIMPLE_HEAD)
    for col in ["Categoria", "Cidade", "Abertas", "Δ mês", *terms, "Salário"]:
        tbl.add_column(col, no_wrap=True,
                       justify="left" if col in ("Categoria", "Cidade") else "right")

    for cat in MARKET_CONFIG["categories"]:
        lines += [f"## {cat}", ""]
        cities = cur.loc[cur["category"] == cat, "city"].unique()

        for city in cities:
            sel   = cur[(cur["category"] == cat) & (cur["city"] == city)].set_index("term")["avg"]
            total = sel.get("")
            p_sel = prev[(prev["category"] == cat) & (prev["city"] == city) & (prev["term"] == "")] \
                    if not prev.empty else pd.DataFrame()
            p_tot = p_sel["avg"].iloc[0] if not p_sel.empty else None
            delta = f"{100 * (total - p_tot) / p_tot:+.0f}%" if p_tot else "—"

            lines += [f"### {city}", "",
                      f"- **Vagas abertas (média diária):** {total:,.0f}"
                      + (f" ({delta} vs. mês anterior)" if p_tot else "")]
            for t in terms:
                n = sel.get(t)
                if n is not None and not pd.isna(n):
                    lines.append(f"- {_TERM_LABELS.get(t, t)}: {n:,.0f} ({_pct(n, total)})")

            med = None
            if not listings.empty:
                ls = listings[(listings["category"] == cat) & (listings["city"] == city)]
                if not ls.empty:
                    uniq  = _dedupe(ls)
                    new   = _dedupe(ls[ls["listed_month"] == month])
                    sal   = uniq["salary_mid"].dropna()
                    lines += [
                        f"- Anúncios vistos no mês: {len(ls):,} → {len(uniq):,} únicos "
                        f"({len(ls) - len(uniq):,} repetidos)",
                        f"- Publicados no mês: {len(new):,}",
                    ]
                    if len(sal):
                        med = sal.median()
                        lines.append(
                            f"- Salário anual (ponto médio da faixa anunciada): mediana {_money(med)}, "
                            f"faixa típica {_money(sal.quantile(.25))}–{_money(sal.quantile(.75))} "
                            f"({len(sal)} de {len(uniq)} anúncios informam salário, "
                            f"{_pct(len(sal), len(uniq))})"
                        )
            lines.append("")

            tbl.add_row(cat, city, f"{total:,.0f}", delta,
                        *[_pct(sel.get(t), total) for t in terms], _money(med))

    lines += [
        "## Metodologia",
        "",
        "- **Vagas abertas**: total de anúncios ativos no Seek na subclassificação, "
        "média dos retratos diários do mês.",
        "- **Menções**: anúncios cujo texto contém o termo, segundo a busca do próprio Seek. "
        "Mede menção, não oferta — \"no sponsorship\" também conta em \"sponsorship\".",
        "- **Repetidos**: mesmo título e empresa na mesma cidade, com IDs diferentes.",
        "- **Salário**: só anúncios que informam valor; por hora × 2.080 h, por dia × 260 dias.",
        "- Dados agregados; nenhuma vaga individual é publicada.",
        "",
    ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"raio-x_{month}.md"
    path.write_text("\n".join(lines), encoding="utf-8")

    console.print(tbl)
    for r in skipped:
        console.print(f"[yellow]Descartado {r['snapshot_date']} ({r['status']}): "
                      f"{(r['issues'] or '').replace(chr(10), '; ')}[/yellow]")
    console.print(f"[green]Relatório salvo em {path}[/green]")
    return path
