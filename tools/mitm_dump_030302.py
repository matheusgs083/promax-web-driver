from urllib.parse import parse_qs


def _first(values, key):
    value = values.get(key)
    if not value:
        return ""
    return value[0]


def response(flow):
    request = flow.request
    url = request.pretty_url or request.url
    body = request.get_text(strict=False) or ""

    if "paubrasil.promaxcloud.com.br" not in url:
        return

    values = parse_qs(body, keep_blank_values=True)
    if not (
        "030302" in url
        or "PW02102C" in url
        or "030302" in body
        or "PW02102C" in body
        or _first(values, "mapa")
        or _first(values, "opcao")
    ):
        return

    response = flow.response
    response_text = response.get_text(strict=False) if response else ""
    response_lower = response_text.lower()
    markers = [
        marker
        for marker in (
            "existem diferen",
            "libera mapa",
            "nao existem",
            "nao existem diferencas",
            "nao existem difer",
            "diferen",
            "msgbx",
            "listaDiferencas",
        )
        if marker.lower() in response_lower
    ]

    print("=== PROMAX FLOW ===")
    print(f"{request.method} {url}")
    print(f"status={response.status_code if response else ''}")
    print(
        "form="
        f"call={_first(values, 'call')} "
        f"opcao={_first(values, 'opcao')} "
        f"mapa={_first(values, 'mapa')} "
        f"mapaSalvo={_first(values, 'mapaSalvo')} "
        f"numeroItems={_first(values, 'numeroItems')} "
        f"idAchouGuiaMapa={_first(values, 'idAchouGuiaMapa')} "
        f"idAchouGuiasSalvas={_first(values, 'idAchouGuiasSalvas')} "
        f"idMostraMsgAfericao={_first(values, 'idMostraMsgAfericao')}"
    )
    itens = _first(values, "itensLista")
    if itens:
        print(f"itensLista_len={len(itens)} prefix={itens[:120]}")
    print(f"response_len={len(response_text)} markers={markers}")
    lower = response_text.lower()
    for marker in (
        "existem diferen",
        "libera mapa",
        "nao existem",
        "listaDiferencas",
        "msgbxSimNao",
    ):
        index = lower.find(marker.lower())
        if index < 0:
            continue
        snippet = response_text[max(0, index - 800) : index + 5000]
        print(
            "snippet_marker="
            + marker
            + " "
            + snippet.replace("\r", "\\r").replace("\n", "\\n")
        )
