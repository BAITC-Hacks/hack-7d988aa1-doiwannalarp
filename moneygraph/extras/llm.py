"""Optional explanation of already computed graph facts."""

import logging
import os
import re

from dotenv import load_dotenv

from moneygraph.extras.queries import common_receivers


LOGGER = logging.getLogger(__name__)


def ask(question: str, G, enriched_df) -> str | None:
    try:
        load_dotenv()
        if not os.getenv("OPENAI_API_KEY"):
            return None

        gids = sorted({int(value) for value in re.findall(r"\b\d+\b", question)})
        known = [gid for gid in gids if gid in G]
        if not known:
            return "Укажите gid узла из наблюдаемого графа."

        lowered = question.lower()
        receiver_intent = any(word in lowered for word in ("собирает", "получает", "связан"))
        rows = []
        if receiver_intent and len(known) >= 2:
            matches = common_receivers(G, known)
            rows.append("Общие достижимые получатели:")
            rows.append(matches.head(20).to_string(index=False) if not matches.empty else "не найдены")
        else:
            indexed = enriched_df.set_index("gid", drop=False)
            for gid in known:
                if gid not in indexed.index:
                    continue
                node = indexed.loc[gid]
                rows.append(
                    f"gid={gid}; роль={node.get('role', '')}; "
                    f"оценка приоритета={node.get('priority_score', '')}; "
                    f"признаки={node.get('evidence', '')}; "
                    f"наблюдаемые входящие={node.get('in_sum', '')} KZT; "
                    f"наблюдаемые исходящие={node.get('out_sum', '')} KZT"
                )
                if "отправляет" in lowered:
                    targets = sorted(G.successors(gid))[:20]
                    rows.append(f"Прямые получатели gid={gid}: {targets}")
                if "кто" in lowered:
                    sources = sorted(G.predecessors(gid))[:20]
                    rows.append(f"Прямые отправители gid={gid}: {sources}")
        facts = "\n".join(rows)

        from openai import OpenAI

        response = OpenAI().chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "Отвечай по-русски только на основании фактов в контексте. Называй выводы гипотезами и признаками. Если данных мало, скажи об этом."},
                {"role": "user", "content": f"Вопрос: {question}\n\nВычисленные факты:\n{facts}"},
            ],
        )
        return response.choices[0].message.content
    except Exception as exc:
        LOGGER.warning("Не удалось получить необязательное объяснение: %s", exc)
        return None
