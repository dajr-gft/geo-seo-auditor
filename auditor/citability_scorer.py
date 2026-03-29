"""
Citability Scorer — Análise de citabilidade por IA.

Avalia blocos de conteúdo quanto à probabilidade de serem citados
por LLMs (ChatGPT, Perplexity, Gemini, etc.).

Baseado em pesquisa empírica sobre passagens citadas por IA:
- Extensão ótima: 134-167 palavras
- Auto-contidas (extraíveis sem contexto)
- Fact-rich com estatísticas específicas
- Estrutura clara de pergunta-resposta

Cada bloco recebe score 0-100 composto por 5 dimensões:
1. Answer Block Quality (30%) — padrões de definição, resposta direta
2. Self-Containment (25%)    — baixa dependência de contexto externo
3. Structural Readability (20%) — clareza e organização
4. Statistical Density (15%)    — dados quantitativos e fontes
5. Uniqueness Signals (10%)     — originalidade e experiência
"""

import re
import logging
from typing import Optional

from config import (
    OPTIMAL_WORD_COUNT_MIN,
    OPTIMAL_WORD_COUNT_MAX,
    MIN_BLOCK_WORDS,
    GRADE_THRESHOLDS,
)

logger = logging.getLogger(__name__)


def score_passage(text: str, heading: Optional[str] = None) -> dict:
    """
    Pontua uma passagem individual para citabilidade por IA (0-100).

    Args:
        text: Conteúdo textual da passagem.
        heading: Heading da seção (opcional, influencia scoring).

    Returns:
        dict com score total, grade, breakdown por dimensão, e metadata.
    """
    words = text.split()
    word_count = len(words)

    scores = {
        "answer_block_quality": 0,
        "self_containment": 0,
        "structural_readability": 0,
        "statistical_density": 0,
        "uniqueness_signals": 0,
    }

    # ═══ 1. Answer Block Quality (30%) ═══
    # Mede se o bloco responde uma pergunta de forma direta e citável.
    abq = 0

    # Padrões de definição ("X is a...", "X refers to...")
    definition_patterns = [
        r"\b\w+\s+is\s+(?:a|an|the)\s",
        r"\b\w+\s+refers?\s+to\s",
        r"\b\w+\s+means?\s",
        r"\b\w+\s+(?:can be |are )?defined\s+as\s",
        r"\bin\s+(?:simple|other)\s+(?:terms|words)\s*,",
        r"\b\w+\s+é\s+(?:um|uma|o|a)\s",         # português
        r"\b\w+\s+refere-se\s+a\s",               # português
        r"\b\w+\s+significa\s",                     # português
    ]
    for pattern in definition_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            abq += 15
            break

    # Resposta aparece cedo (primeiras 60 palavras)
    first_60 = " ".join(words[:60])
    early_answer_patterns = [
        r"\b(?:is|are|was|were|means?|refers?|é|são|foi|significa)\b",
        r"\d+%",
        r"(?:R\$|\$|€|£)[\d,]+",
        r"\d+\s+(?:million|billion|thousand|milhões|bilhões|mil)",
    ]
    if any(re.search(p, first_60, re.IGNORECASE) for p in early_answer_patterns):
        abq += 15

    # Heading em formato de pergunta (bonus)
    if heading and heading.rstrip().endswith("?"):
        abq += 10

    # Sentenças claras e diretas (5-25 palavras)
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if sentences:
        short_clear = sum(1 for s in sentences if 5 <= len(s.split()) <= 25)
        clarity_ratio = short_clear / len(sentences)
        abq += int(clarity_ratio * 10)

    # Claims quotáveis com fonte
    source_claims = [
        r"(?:according to|de acordo com|segundo|conforme)",
        r"(?:research|pesquisa|estudo)\s+(?:shows?|indica|mostra)",
        r"(?:studies?|estudos)\s+(?:show|indicate|suggest|found|mostram|indicam)",
        r"(?:data|dados)\s+(?:shows?|indica|mostra|suggests?|sugere)",
    ]
    if any(re.search(p, text, re.IGNORECASE) for p in source_claims):
        abq += 10

    scores["answer_block_quality"] = min(abq, 30)

    # ═══ 2. Self-Containment (25%) ═══
    # Mede se o bloco pode ser extraído sem precisar de contexto externo.
    sc = 0

    # Contagem de palavras na faixa ótima
    if OPTIMAL_WORD_COUNT_MIN <= word_count <= OPTIMAL_WORD_COUNT_MAX:
        sc += 10
    elif 100 <= word_count <= 200:
        sc += 7
    elif 80 <= word_count <= 250:
        sc += 4
    elif word_count < 30 or word_count > 400:
        sc += 0
    else:
        sc += 2

    # Densidade de pronomes (menos pronomes = mais auto-contido)
    pronouns = re.findall(
        r"\b(?:it|they|them|their|this|that|these|those|he|she|his|her"
        r"|ele|ela|eles|elas|isso|isto|aquilo|seu|sua|seus|suas|dele|dela)\b",
        text, re.IGNORECASE,
    )
    if word_count > 0:
        pronoun_ratio = len(pronouns) / word_count
        if pronoun_ratio < 0.02:
            sc += 8
        elif pronoun_ratio < 0.04:
            sc += 5
        elif pronoun_ratio < 0.06:
            sc += 3

    # Entidades nomeadas (nomes próprios = contexto embutido)
    proper_nouns = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
    if len(proper_nouns) >= 3:
        sc += 7
    elif len(proper_nouns) >= 1:
        sc += 4

    scores["self_containment"] = min(sc, 25)

    # ═══ 3. Structural Readability (20%) ═══
    # Mede clareza estrutural do conteúdo.
    sr = 0

    # Tamanho médio de sentença
    if sentences:
        avg_sent_len = word_count / len(sentences)
        if 10 <= avg_sent_len <= 20:
            sr += 8
        elif 8 <= avg_sent_len <= 25:
            sr += 5
        else:
            sr += 2

    # Marcadores de sequência/lista
    sequence_markers = [
        r"(?:first|second|third|finally|additionally|moreover|furthermore)",
        r"(?:primeiro|segundo|terceiro|finalmente|além disso|ademais)",
        r"(?:primeiramente|em seguida|por fim|por último)",
    ]
    if any(re.search(p, text, re.IGNORECASE) for p in sequence_markers):
        sr += 4

    # Itens numerados ou steps
    if re.search(r"(?:\d+[\.\)]\s|\b(?:step|tip|point|passo|dica|etapa)\s+\d+)", text, re.IGNORECASE):
        sr += 4

    # Quebras de parágrafo (indica estrutura)
    if "\n" in text:
        sr += 4

    scores["structural_readability"] = min(sr, 20)

    # ═══ 4. Statistical Density (15%) ═══
    # Mede presença de dados quantitativos e referências temporais.
    sd = 0

    # Percentuais
    pct_count = len(re.findall(r"\d+(?:\.\d+)?%", text))
    sd += min(pct_count * 3, 6)

    # Valores monetários
    money_count = len(re.findall(
        r"(?:R\$|\$|€|£)\s*[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|mil|milhões|bilhões|M|B|K))?",
        text
    ))
    sd += min(money_count * 3, 5)

    # Números com contexto
    contextualized_nums = len(re.findall(
        r"\b\d+(?:,\d{3})*(?:\.\d+)?\s+(?:users|customers|pages|sites|companies|"
        r"businesses|people|percent|times|x\b|usuários|clientes|empresas|pessoas|vezes)",
        text, re.IGNORECASE,
    ))
    sd += min(contextualized_nums * 2, 4)

    # Referências temporais (anos recentes)
    if re.findall(r"\b20(?:2[3-7]|1\d)\b", text):
        sd += 2

    scores["statistical_density"] = min(sd, 15)

    # ═══ 5. Uniqueness Signals (10%) ═══
    # Mede originalidade e experiência demonstrada.
    us = 0

    # Indicadores de dados originais
    original_data = [
        r"(?:our (?:research|study|data|analysis|survey|findings))",
        r"(?:we (?:found|discovered|analyzed|surveyed|measured))",
        r"(?:nossa (?:pesquisa|análise|experiência))",
        r"(?:nós (?:descobrimos|analisamos|identificamos))",
    ]
    if any(re.search(p, text, re.IGNORECASE) for p in original_data):
        us += 5

    # Case studies / exemplos práticos
    case_study = [
        r"(?:case study|for example|for instance|in practice|real-world|hands-on)",
        r"(?:estudo de caso|por exemplo|na prática|caso real)",
    ]
    if any(re.search(p, text, re.IGNORECASE) for p in case_study):
        us += 3

    # Menção de ferramenta/produto específico
    if re.search(r"(?:using|with|via|through|usando|com|através)\s+[A-Z][a-z]+", text):
        us += 2

    scores["uniqueness_signals"] = min(us, 10)

    # ═══ Score total e grade ═══
    raw_total = sum(scores.values())

    # ═══ Multiplicador de viabilidade por extensão ═══
    # IAs citam passagens de tamanho ideal (134-167 palavras).
    # Blocos muito curtos ou muito longos são fundamentalmente
    # menos citáveis, independente do conteúdo.
    if OPTIMAL_WORD_COUNT_MIN <= word_count <= OPTIMAL_WORD_COUNT_MAX:
        length_multiplier = 1.0  # faixa ideal — score completo
    elif 100 <= word_count <= 200:
        length_multiplier = 0.92  # próximo do ideal
    elif 80 <= word_count <= 250:
        length_multiplier = 0.82  # aceitável
    elif 60 <= word_count <= 300:
        length_multiplier = 0.70  # abaixo do ideal
    elif 50 <= word_count <= 400:
        length_multiplier = 0.60  # marginal
    else:
        length_multiplier = 0.50  # muito curto ou muito longo

    total = max(0, min(100, round(raw_total * length_multiplier)))

    grade = "F"
    label = "Poor Citability"
    for g, threshold in sorted(GRADE_THRESHOLDS.items(), key=lambda x: -x[1]):
        if total >= threshold:
            grade = g
            label = {
                "A": "Highly Citable",
                "B": "Good Citability",
                "C": "Moderate Citability",
                "D": "Low Citability",
                "F": "Poor Citability",
            }[g]
            break

    return {
        "heading": heading,
        "word_count": word_count,
        "total_score": total,
        "grade": grade,
        "label": label,
        "breakdown": scores,
        "preview": " ".join(words[:30]) + ("..." if word_count > 30 else ""),
        "is_optimal_length": OPTIMAL_WORD_COUNT_MIN <= word_count <= OPTIMAL_WORD_COUNT_MAX,
        "source_url": None,  # populated by caller
    }


def analyze_page_citability(content_blocks: list[dict]) -> dict:
    """
    Analisa todos os blocos de conteúdo de uma página.

    Args:
        content_blocks: Lista de {heading, content, word_count} do page_fetcher.

    Returns:
        dict com scores por bloco, métricas agregadas e distribuição de grades.
    """
    if not content_blocks:
        return {
            "total_blocks_analyzed": 0,
            "average_score": 0,
            "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
            "optimal_length_count": 0,
            "scored_blocks": [],
            "top_5": [],
            "bottom_5": [],
        }

    scored_blocks = []
    for block in content_blocks:
        score = score_passage(block["content"], block.get("heading"))
        score["source_url"] = block.get("source_url")
        scored_blocks.append(score)

    # ── Métricas agregadas ──
    avg_score = sum(b["total_score"] for b in scored_blocks) / len(scored_blocks)
    optimal_count = sum(1 for b in scored_blocks if b["is_optimal_length"])

    # Distribuição de grades
    grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for block in scored_blocks:
        grade_dist[block["grade"]] += 1

    # Top e bottom 5
    sorted_blocks = sorted(scored_blocks, key=lambda x: x["total_score"], reverse=True)
    top_5 = sorted_blocks[:5]
    bottom_5 = sorted_blocks[-5:]

    # Score da categoria (normalizado 0-100)
    category_score = round(avg_score)

    logger.info(
        "Citability analysis: %d blocks, avg %.1f, %d optimal length, grades: %s",
        len(scored_blocks), avg_score, optimal_count, grade_dist,
    )

    return {
        "total_blocks_analyzed": len(scored_blocks),
        "average_score": round(avg_score, 1),
        "category_score": category_score,
        "grade_distribution": grade_dist,
        "optimal_length_count": optimal_count,
        "scored_blocks": scored_blocks,
        "top_5": top_5,
        "bottom_5": bottom_5,
    }
