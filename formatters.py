def build_message_text(results: dict[str, list[tuple[str, str]]]) -> str:
    lines: list[str] = []

    for display_name, mall_results in results.items():
        lines.append(f"*{display_name}")

        for mall_display, price in mall_results:
            shown_price = price if price else ""
            lines.append(f"{mall_display} - {shown_price}")

        lines.append("")

    return "\n".join(lines).strip()
