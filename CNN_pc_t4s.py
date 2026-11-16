import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from html import escape
import unicodedata
import subprocess
import tempfile
import json
import os
import time

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.table import Table, TableStyleInfo


# ================================================================
# CONFIGURACAO
# ================================================================

URL_CNN = "https://www.cnnbrasil.com.br/sitemap-news.xml"

DESTINATARIO_EMAIL = "igor.franca@fedex.com"

ASSUNTO_EMAIL = "Monitor de Noticias CNN Brasil"

FUSO_BRASIL = timezone(
    timedelta(hours=-3)
)

NAMESPACES = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "news": "http://www.google.com/schemas/sitemap-news/0.9"
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9"
}


# ================================================================
# TEMAS E PALAVRAS-CHAVE
# ================================================================

TEMAS = {
    "Seguranca": [
        "polícia",
        "roubo",
        "furto",
        "assalto",
        "tiroteio",
        "violência",
        "operação policial",
        "criminosos",
        "facção"
    ],

    "Desastres e Operacoes": [
        "incêndio",
        "enchente",
        "alagamento",
        "explosão",
        "acidente",
        "desabamento",
        "temporal"
    ],

    "Logistica": [
        "rodovia",
        "aeroporto",
        "greve",
        "bloqueio",
        "interdição",
        "trânsito",
        "caminhoneiros"
    ],

    "Tecnologia e Seguranca Digital": [
        "ataque hacker",
        "ciberataque",
        "ransomware",
        "vazamento de dados",
        "fraude",
        "inteligência artificial"
    ]
}


# ================================================================
# NORMALIZACAO E CLASSIFICACAO
# ================================================================

def normalizar_texto(texto):

    if not texto:
        return ""

    texto = str(texto).lower()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    return texto


def classificar_noticia(
    titulo,
    descricao,
    conteudo
):

    texto_completo = normalizar_texto(
        f"{titulo} {descricao} {conteudo}"
    )

    temas_encontrados = []
    palavras_encontradas = []

    for tema, palavras in TEMAS.items():

        encontrou_tema = False

        for palavra in palavras:

            palavra_normalizada = normalizar_texto(
                palavra
            )

            if palavra_normalizada in texto_completo:

                encontrou_tema = True

                if palavra not in palavras_encontradas:
                    palavras_encontradas.append(
                        palavra
                    )

        if encontrou_tema:
            temas_encontrados.append(
                tema
            )

    return temas_encontrados, palavras_encontradas


# ================================================================
# LEITOR DE META TAGS
# ================================================================

class MetaParser(HTMLParser):

    def __init__(self):

        super().__init__()

        self.metadados = {}

    def handle_starttag(
        self,
        tag,
        attrs
    ):

        if tag.lower() != "meta":
            return

        atributos = dict(attrs)

        chave = (
            atributos.get("property")
            or atributos.get("name")
            or ""
        ).lower()

        conteudo = atributos.get(
            "content",
            ""
        ).strip()

        if chave and conteudo:
            self.metadados[chave] = conteudo


# ================================================================
# LEITOR DE JSON-LD
# ================================================================

class JSONLDParser(HTMLParser):

    def __init__(self):

        super().__init__()

        self.capturando = False
        self.conteudo_atual = []
        self.blocos = []

    def handle_starttag(
        self,
        tag,
        attrs
    ):

        if tag.lower() != "script":
            return

        atributos = dict(attrs)

        tipo = atributos.get(
            "type",
            ""
        ).lower()

        if tipo == "application/ld+json":

            self.capturando = True
            self.conteudo_atual = []

    def handle_data(
        self,
        data
    ):

        if self.capturando:

            self.conteudo_atual.append(
                data
            )

    def handle_endtag(
        self,
        tag
    ):

        if (
            tag.lower() == "script"
            and self.capturando
        ):

            conteudo = "".join(
                self.conteudo_atual
            ).strip()

            if conteudo:

                self.blocos.append(
                    conteudo
                )

            self.capturando = False
            self.conteudo_atual = []


# ================================================================
# REQUISICOES
# ================================================================

def fazer_requisicao(
    url,
    timeout=30
):

    requisicao = urllib.request.Request(
        url,
        headers=HEADERS
    )

    with urllib.request.urlopen(
        requisicao,
        timeout=timeout
    ) as resposta:

        return resposta.read()


def baixar_sitemap():

    try:

        return fazer_requisicao(
            URL_CNN
        )

    except urllib.error.HTTPError as erro:

        print()
        print("Erro HTTP ao acessar a CNN.")
        print("Codigo:", erro.code)
        print("Motivo:", erro.reason)

    except urllib.error.URLError as erro:

        print()
        print("Erro de conexao ao acessar a CNN.")
        print(erro)

    except Exception as erro:

        print()
        print("Erro inesperado ao acessar a CNN.")
        print(erro)

    return None


# ================================================================
# FUNCOES AUXILIARES
# ================================================================

def obter_texto(elemento):

    if elemento is None:
        return ""

    return (
        elemento.text or ""
    ).strip()


def formatar_data_iso(data_iso):

    if not data_iso:
        return "Nao informado"

    try:

        data_hora = datetime.fromisoformat(
            data_iso.replace(
                "Z",
                "+00:00"
            )
        )

        if data_hora.tzinfo is not None:

            data_hora = data_hora.astimezone(
                FUSO_BRASIL
            )

        return data_hora.strftime(
            "%d/%m/%Y %H:%M"
        )

    except ValueError:

        return data_iso


def obter_nome_autor(autor):

    if isinstance(autor, str):

        return autor.strip()

    if isinstance(autor, dict):

        return str(
            autor.get(
                "name",
                ""
            )
        ).strip()

    if isinstance(autor, list):

        nomes = []

        for pessoa in autor:

            if isinstance(pessoa, dict):

                nome = str(
                    pessoa.get(
                        "name",
                        ""
                    )
                ).strip()

            elif isinstance(pessoa, str):

                nome = pessoa.strip()

            else:

                nome = ""

            if nome:

                nomes.append(
                    nome
                )

        return ", ".join(
            nomes
        )

    return ""


def obter_url_imagem(imagem):

    if isinstance(imagem, str):

        return imagem.strip()

    if isinstance(imagem, dict):

        return str(
            imagem.get(
                "url",
                ""
            )
        ).strip()

    if isinstance(imagem, list) and imagem:

        primeira_imagem = imagem[0]

        if isinstance(
            primeira_imagem,
            str
        ):

            return primeira_imagem.strip()

        if isinstance(
            primeira_imagem,
            dict
        ):

            return str(
                primeira_imagem.get(
                    "url",
                    ""
                )
            ).strip()

    return ""


# ================================================================
# LOCALIZAR ARTIGO NO JSON-LD
# ================================================================

def procurar_artigo_json(dados):

    if isinstance(dados, list):

        for item in dados:

            artigo = procurar_artigo_json(
                item
            )

            if artigo:
                return artigo

        return None

    if not isinstance(dados, dict):
        return None

    tipo = dados.get(
        "@type",
        ""
    )

    if isinstance(tipo, list):
        tipos = tipo
    else:
        tipos = [tipo]

    tipos_validos = {
        "Article",
        "NewsArticle",
        "ReportageNewsArticle",
        "BlogPosting"
    }

    if any(
        tipo_artigo in tipos_validos
        for tipo_artigo in tipos
    ):

        return dados

    grafo = dados.get(
        "@graph"
    )

    if grafo:

        artigo = procurar_artigo_json(
            grafo
        )

        if artigo:
            return artigo

    for valor in dados.values():

        if isinstance(
            valor,
            (dict, list)
        ):

            artigo = procurar_artigo_json(
                valor
            )

            if artigo:
                return artigo

    return None


# ================================================================
# OBTER DETALHES DA NOTICIA
# ================================================================

def obter_detalhes_noticia(url):

    resultado = {
        "titulo": "",
        "descricao": "",
        "categoria": "",
        "autor": "",
        "publicado": "",
        "atualizado": "",
        "conteudo": "",
        "imagem": "",
        "erro": ""
    }

    try:

        dados_html = fazer_requisicao(
            url
        )

        pagina_html = dados_html.decode(
            "utf-8",
            errors="ignore"
        )

    except Exception as erro:

        resultado["erro"] = str(
            erro
        )

        return resultado

    # ------------------------------------------------------------
    # META TAGS
    # ------------------------------------------------------------

    parser_meta = MetaParser()

    parser_meta.feed(
        pagina_html
    )

    metas = parser_meta.metadados

    resultado["titulo"] = (
        metas.get("og:title", "")
        or metas.get("twitter:title", "")
    )

    resultado["descricao"] = (
        metas.get("og:description", "")
        or metas.get("description", "")
        or metas.get("twitter:description", "")
    )

    resultado["categoria"] = metas.get(
        "article:section",
        ""
    )

    resultado["autor"] = (
        metas.get("author", "")
        or metas.get("article:author", "")
    )

    resultado["publicado"] = metas.get(
        "article:published_time",
        ""
    )

    resultado["atualizado"] = metas.get(
        "article:modified_time",
        ""
    )

    resultado["imagem"] = (
        metas.get("og:image", "")
        or metas.get("twitter:image", "")
    )

    # ------------------------------------------------------------
    # JSON-LD
    # ------------------------------------------------------------

    parser_json = JSONLDParser()

    parser_json.feed(
        pagina_html
    )

    for bloco in parser_json.blocos:

        try:

            dados_json = json.loads(
                bloco
            )

        except (
            json.JSONDecodeError,
            TypeError
        ):

            continue

        artigo = procurar_artigo_json(
            dados_json
        )

        if not artigo:
            continue

        resultado["titulo"] = (
            artigo.get("headline")
            or artigo.get("name")
            or resultado["titulo"]
        )

        resultado["descricao"] = (
            artigo.get("description")
            or resultado["descricao"]
        )

        resultado["categoria"] = (
            artigo.get("articleSection")
            or resultado["categoria"]
        )

        resultado["autor"] = (
            obter_nome_autor(
                artigo.get("author")
            )
            or resultado["autor"]
        )

        resultado["publicado"] = (
            artigo.get("datePublished")
            or resultado["publicado"]
        )

        resultado["atualizado"] = (
            artigo.get("dateModified")
            or resultado["atualizado"]
        )

        resultado["conteudo"] = (
            artigo.get("articleBody")
            or resultado["conteudo"]
        )

        resultado["imagem"] = (
            obter_url_imagem(
                artigo.get("image")
            )
            or resultado["imagem"]
        )

        break

    return resultado


# ================================================================
# EXTRAIR NOTICIAS DA DATA
# ================================================================

def extrair_noticias_da_data(
    xml,
    data_desejada
):

    try:

        raiz = ET.fromstring(
            xml
        )

    except ET.ParseError as erro:

        print()
        print("Erro ao interpretar o sitemap:")
        print(erro)

        return []

    noticias = []

    for item in raiz.findall(
        "sm:url",
        NAMESPACES
    ):

        link = obter_texto(
            item.find(
                "sm:loc",
                NAMESPACES
            )
        )

        titulo = obter_texto(
            item.find(
                "news:news/news:title",
                NAMESPACES
            )
        )

        data_publicacao = obter_texto(
            item.find(
                "news:news/news:publication_date",
                NAMESPACES
            )
        )

        if not link or not data_publicacao:
            continue

        try:

            data_hora = datetime.fromisoformat(
                data_publicacao.replace(
                    "Z",
                    "+00:00"
                )
            )

            if data_hora.tzinfo is not None:

                data_hora_brasil = data_hora.astimezone(
                    FUSO_BRASIL
                )

            else:

                data_hora_brasil = data_hora.replace(
                    tzinfo=FUSO_BRASIL
                )

        except ValueError:

            continue

        data_noticia = data_hora_brasil.strftime(
            "%d/%m/%Y"
        )

        if data_noticia != data_desejada:
            continue

        noticias.append({
            "titulo": titulo,
            "data": data_noticia,
            "hora": data_hora_brasil.strftime(
                "%H:%M"
            ),
            "data_iso": data_hora_brasil.isoformat(),
            "link": link
        })

    noticias.sort(
        key=lambda noticia: noticia.get(
            "data_iso",
            ""
        ),
        reverse=True
    )

    return noticias


# ================================================================
# CORES DOS TEMAS
# ================================================================

def obter_cor_tema(tema):

    cores = {
        "Seguranca": "#C62828",
        "Desastres e Operacoes": "#EF6C00",
        "Logistica": "#1565C0",
        "Tecnologia e Seguranca Digital": "#6A1B9A"
    }

    temas_separados = [
        item.strip()
        for item in tema.split(",")
        if item.strip()
    ]

    for item in temas_separados:

        if item in cores:
            return cores[item]

    return "#37474F"


# ================================================================
# MONTAR HTML DO EMAIL
# ================================================================

def montar_corpo_email_html(
    data_desejada,
    total_analisadas,
    noticias_filtradas
):

    agora_brasil = datetime.now(
        FUSO_BRASIL
    )

    contagem_temas = {}

    for tema in TEMAS:

        contagem_temas[tema] = sum(
            1
            for noticia in noticias_filtradas
            if tema in noticia.get(
                "tema",
                ""
            )
        )

    resumo_temas_html = ""

    for tema, quantidade in contagem_temas.items():

        resumo_temas_html += f"""
        <td style="padding:8px;vertical-align:top;">
            <table
                role="presentation"
                width="100%"
                cellspacing="0"
                cellpadding="0"
                border="0"
                style="
                    border-collapse:collapse;
                    background-color:#F3F4F6;
                    border:1px solid #E5E7EB;
                "
            >
                <tr>
                    <td style="
                        padding:12px;
                        text-align:center;
                        font-family:Arial,Helvetica,sans-serif;
                    ">
                        <div style="
                            color:#374151;
                            font-size:12px;
                            font-weight:bold;
                            line-height:18px;
                        ">
                            {escape(tema)}
                        </div>

                        <div style="
                            margin-top:4px;
                            color:#B71C1C;
                            font-size:24px;
                            font-weight:bold;
                            line-height:30px;
                        ">
                            {quantidade}
                        </div>
                    </td>
                </tr>
            </table>
        </td>
        """

    noticias_html = ""

    if not noticias_filtradas:

        noticias_html = """
        <table
            role="presentation"
            width="100%"
            cellspacing="0"
            cellpadding="0"
            border="0"
            style="
                border-collapse:collapse;
                margin-top:20px;
                background-color:#FFF8E1;
                border:1px solid #FFE082;
            "
        >
            <tr>
                <td style="
                    padding:24px;
                    text-align:center;
                    color:#795548;
                    font-family:Arial,Helvetica,sans-serif;
                    font-size:15px;
                    line-height:22px;
                ">
                    Nenhuma matéria correspondente aos temas monitorados
                    foi encontrada nesta consulta.
                </td>
            </tr>
        </table>
        """

    else:

        for numero, noticia in enumerate(
            noticias_filtradas,
            start=1
        ):

            tema_original = str(
                noticia.get(
                    "tema",
                    "Não informado"
                )
            )

            cor_tema = obter_cor_tema(
                tema_original
            )

            titulo = escape(
                str(
                    noticia.get(
                        "titulo",
                        "Título não informado"
                    )
                )
            )

            descricao = escape(
                str(
                    noticia.get(
                        "descricao",
                        "Não informado"
                    )
                )
            )

            tema = escape(
                tema_original
            )

            palavras = escape(
                str(
                    noticia.get(
                        "palavras_encontradas",
                        "Não informado"
                    )
                )
            )

            categoria = escape(
                str(
                    noticia.get(
                        "categoria",
                        "Não informado"
                    )
                )
            )

            autor = escape(
                str(
                    noticia.get(
                        "autor",
                        "Não informado"
                    )
                )
            )

            publicado = escape(
                str(
                    noticia.get(
                        "publicado",
                        "Não informado"
                    )
                )
            )

            atualizado = escape(
                str(
                    noticia.get(
                        "atualizado",
                        "Não informado"
                    )
                )
            )

            link_original = str(
                noticia.get(
                    "link",
                    ""
                )
            ).strip()

            link = escape(
                link_original,
                quote=True
            )

            imagem_original = str(
                noticia.get(
                    "imagem",
                    ""
                )
            ).strip()

            imagem = escape(
                imagem_original,
                quote=True
            )

            imagem_html = ""

            if imagem_original.startswith(
                ("http://", "https://")
            ):

                imagem_html = f"""
                <tr>
                    <td
                        align="center"
                        style="padding:18px 20px 5px 20px;"
                    >
                        <img
                            src="{imagem}"
                            alt="{titulo}"
                            width="400"
                            style="
                                display:block;
                                width:400px;
                                max-width:100%;
                                height:auto;
                                border:0;
                                margin:0 auto;
                            "
                        >
                    </td>
                </tr>
                """

            botao_html = ""

            if link_original.startswith(
                ("http://", "https://")
            ):

                botao_html = f"""
                <table
                    role="presentation"
                    cellspacing="0"
                    cellpadding="0"
                    border="0"
                    style="
                        border-collapse:collapse;
                        margin-top:18px;
                    "
                >
                    <tr>
                        <td
                            bgcolor="#B71C1C"
                            style="
                                background-color:#B71C1C;
                                border-radius:4px;
                            "
                        >
                            <a
                                href="{link}"
                                style="
                                    display:inline-block;
                                    padding:12px 20px;
                                    color:#FFFFFF;
                                    font-family:Arial,Helvetica,sans-serif;
                                    font-size:14px;
                                    font-weight:bold;
                                    text-decoration:none;
                                "
                            >
                                Acessar matéria completa
                            </a>
                        </td>
                    </tr>
                </table>
                """

            noticias_html += f"""
            <table
                role="presentation"
                width="100%"
                cellspacing="0"
                cellpadding="0"
                border="0"
                style="
                    width:100%;
                    border-collapse:collapse;
                    margin-top:24px;
                    background-color:#FFFFFF;
                    border:1px solid #D1D5DB;
                "
            >
                <tr>
                    <td
                        bgcolor="{cor_tema}"
                        style="
                            padding:10px 18px;
                            background-color:{cor_tema};
                            color:#FFFFFF;
                            font-family:Arial,Helvetica,sans-serif;
                            font-size:13px;
                            font-weight:bold;
                        "
                    >
                        MATÉRIA {numero} &nbsp;|&nbsp; {tema}
                    </td>
                </tr>

                {imagem_html}

                <tr>
                    <td style="padding:22px;">
                        <h2 style="
                            margin:0 0 12px 0;
                            color:#111827;
                            font-family:Arial,Helvetica,sans-serif;
                            font-size:21px;
                            line-height:29px;
                        ">
                            {titulo}
                        </h2>

                        <p style="
                            margin:0 0 18px 0;
                            color:#4B5563;
                            font-family:Arial,Helvetica,sans-serif;
                            font-size:15px;
                            line-height:23px;
                        ">
                            {descricao}
                        </p>

                        <table
                            role="presentation"
                            width="100%"
                            cellspacing="0"
                            cellpadding="0"
                            border="0"
                            style="
                                width:100%;
                                border-collapse:collapse;
                                background-color:#F9FAFB;
                                border:1px solid #E5E7EB;
                            "
                        >
                            <tr>
                                <td style="
                                    width:150px;
                                    padding:9px 12px;
                                    border-bottom:1px solid #E5E7EB;
                                    color:#374151;
                                    font-family:Arial,Helvetica,sans-serif;
                                    font-size:13px;
                                    font-weight:bold;
                                ">
                                    Categoria
                                </td>

                                <td style="
                                    padding:9px 12px;
                                    border-bottom:1px solid #E5E7EB;
                                    color:#4B5563;
                                    font-family:Arial,Helvetica,sans-serif;
                                    font-size:13px;
                                ">
                                    {categoria}
                                </td>
                            </tr>

                            <tr>
                                <td style="
                                    width:150px;
                                    padding:9px 12px;
                                    border-bottom:1px solid #E5E7EB;
                                    color:#374151;
                                    font-family:Arial,Helvetica,sans-serif;
                                    font-size:13px;
                                    font-weight:bold;
                                ">
                                    Autor
                                </td>

                                <td style="
                                    padding:9px 12px;
                                    border-bottom:1px solid #E5E7EB;
                                    color:#4B5563;
                                    font-family:Arial,Helvetica,sans-serif;
                                    font-size:13px;
                                ">
                                    {autor}
                                </td>
                            </tr>

                            <tr>
                                <td style="
                                    width:150px;
                                    padding:9px 12px;
                                    border-bottom:1px solid #E5E7EB;
                                    color:#374151;
                                    font-family:Arial,Helvetica,sans-serif;
                                    font-size:13px;
                                    font-weight:bold;
                                ">
                                    Publicado
                                </td>

                                <td style="
                                    padding:9px 12px;
                                    border-bottom:1px solid #E5E7EB;
                                    color:#4B5563;
                                    font-family:Arial,Helvetica,sans-serif;
                                    font-size:13px;
                                ">
                                    {publicado}
                                </td>
                            </tr>

                            <tr>
                                <td style="
                                    width:150px;
                                    padding:9px 12px;
                                    border-bottom:1px solid #E5E7EB;
                                    color:#374151;
                                    font-family:Arial,Helvetica,sans-serif;
                                    font-size:13px;
                                    font-weight:bold;
                                ">
                                    Atualizado
                                </td>

                                <td style="
                                    padding:9px 12px;
                                    border-bottom:1px solid #E5E7EB;
                                    color:#4B5563;
                                    font-family:Arial,Helvetica,sans-serif;
                                    font-size:13px;
                                ">
                                    {atualizado}
                                </td>
                            </tr>

                            <tr>
                                <td style="
                                    width:150px;
                                    padding:9px 12px;
                                    color:#374151;
                                    font-family:Arial,Helvetica,sans-serif;
                                    font-size:13px;
                                    font-weight:bold;
                                ">
                                    Palavras identificadas
                                </td>

                                <td style="
                                    padding:9px 12px;
                                    color:#4B5563;
                                    font-family:Arial,Helvetica,sans-serif;
                                    font-size:13px;
                                ">
                                    {palavras}
                                </td>
                            </tr>
                        </table>

                        {botao_html}
                    </td>
                </tr>
            </table>
            """

    corpo_html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>
            Monitor de Notícias CNN Brasil
        </title>
    </head>

    <body style="
        margin:0;
        padding:0;
        background-color:#E5E7EB;
    ">
        <table
            role="presentation"
            width="100%"
            cellspacing="0"
            cellpadding="0"
            border="0"
            bgcolor="#E5E7EB"
            style="
                width:100%;
                border-collapse:collapse;
                background-color:#E5E7EB;
            "
        >
            <tr>
                <td
                    align="center"
                    style="padding:24px 10px;"
                >
                    <table
                        role="presentation"
                        width="740"
                        cellspacing="0"
                        cellpadding="0"
                        border="0"
                        style="
                            width:100%;
                            max-width:740px;
                            border-collapse:collapse;
                            background-color:#FFFFFF;
                        "
                    >
                        <tr>
                            <td
                                bgcolor="#B71C1C"
                                style="
                                    padding:28px 30px;
                                    background-color:#B71C1C;
                                    color:#FFFFFF;
                                    font-family:Arial,Helvetica,sans-serif;
                                "
                            >
                                <div style="
                                    font-size:27px;
                                    font-weight:bold;
                                    line-height:34px;
                                ">
                                    Monitor de Notícias
                                </div>

                                <div style="
                                    margin-top:4px;
                                    font-size:16px;
                                    line-height:23px;
                                ">
                                    CNN Brasil
                                </div>
                            </td>
                        </tr>

                        <tr>
                            <td style="
                                padding:30px;
                                font-family:Arial,Helvetica,sans-serif;
                            ">
                                <p style="
                                    margin:0 0 10px 0;
                                    color:#111827;
                                    font-size:16px;
                                    line-height:24px;
                                ">
                                    Bom dia,
                                </p>

                                <p style="
                                    margin:0 0 22px 0;
                                    color:#4B5563;
                                    font-size:15px;
                                    line-height:23px;
                                ">
                                    Segue o resultado da consulta automatizada
                                    realizada no portal CNN Brasil.
                                </p>

                                <table
                                    role="presentation"
                                    width="100%"
                                    cellspacing="0"
                                    cellpadding="0"
                                    border="0"
                                    style="
                                        width:100%;
                                        border-collapse:collapse;
                                        background-color:#F9FAFB;
                                        border:1px solid #E5E7EB;
                                    "
                                >
                                    <tr>
                                        <td style="
                                            padding:11px 14px;
                                            border-bottom:1px solid #E5E7EB;
                                            color:#374151;
                                            font-size:14px;
                                            font-weight:bold;
                                        ">
                                            Data da consulta
                                        </td>

                                        <td style="
                                            padding:11px 14px;
                                            border-bottom:1px solid #E5E7EB;
                                            color:#4B5563;
                                            font-size:14px;
                                        ">
                                            {escape(data_desejada)}
                                        </td>
                                    </tr>

                                    <tr>
                                        <td style="
                                            padding:11px 14px;
                                            border-bottom:1px solid #E5E7EB;
                                            color:#374151;
                                            font-size:14px;
                                            font-weight:bold;
                                        ">
                                            Matérias analisadas
                                        </td>

                                        <td style="
                                            padding:11px 14px;
                                            border-bottom:1px solid #E5E7EB;
                                            color:#4B5563;
                                            font-size:14px;
                                        ">
                                            {total_analisadas}
                                        </td>
                                    </tr>

                                    <tr>
                                        <td style="
                                            padding:11px 14px;
                                            color:#374151;
                                            font-size:14px;
                                            font-weight:bold;
                                        ">
                                            Notícias relevantes
                                        </td>

                                        <td style="
                                            padding:11px 14px;
                                            color:#B71C1C;
                                            font-size:15px;
                                            font-weight:bold;
                                        ">
                                            {len(noticias_filtradas)}
                                        </td>
                                    </tr>
                                </table>

                                <div style="
                                    margin-top:28px;
                                    margin-bottom:10px;
                                    color:#111827;
                                    font-size:18px;
                                    font-weight:bold;
                                ">
                                    Resumo por tema
                                </div>

                                <table
                                    role="presentation"
                                    width="100%"
                                    cellspacing="0"
                                    cellpadding="0"
                                    border="0"
                                    style="
                                        width:100%;
                                        border-collapse:collapse;
                                    "
                                >
                                    <tr>
                                        {resumo_temas_html}
                                    </tr>
                                </table>

                                <div style="
                                    margin-top:30px;
                                    color:#111827;
                                    font-size:20px;
                                    font-weight:bold;
                                ">
                                    Matérias identificadas
                                </div>

                                {noticias_html}
                            </td>
                        </tr>

                        <tr>
                            <td
                                bgcolor="#111827"
                                style="
                                    padding:20px 30px;
                                    background-color:#111827;
                                    color:#D1D5DB;
                                    text-align:center;
                                    font-family:Arial,Helvetica,sans-serif;
                                    font-size:12px;
                                    line-height:19px;
                                "
                            >
                                Mensagem gerada automaticamente pelo
                                Monitor de Notícias CNN Brasil.<br>

                                Gerado em:
                                {agora_brasil.strftime("%d/%m/%Y %H:%M:%S")}
                                | Fuso horário UTC-03:00
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    return corpo_html


# ================================================================
# CRIAR EXCEL A PARTIR DE JSON
# ================================================================

def criar_excel_noticias(
    noticias_filtradas,
    data_desejada
):

    agora_brasil = datetime.now(
        FUSO_BRASIL
    )

    identificador = agora_brasil.strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    nome_json = (
        "cnn_dados_"
        + identificador
        + ".json"
    )

    nome_excel = (
        "Noticias_CNN_"
        + identificador
        + ".xlsx"
    )

    caminho_json = os.path.join(
        tempfile.gettempdir(),
        nome_json
    )

    caminho_excel = os.path.join(
        tempfile.gettempdir(),
        nome_excel
    )

    dados_para_json = []

    for noticia in noticias_filtradas:

        dados_para_json.append({
            "Data": noticia.get(
                "data",
                data_desejada
            ),

            "Hora": noticia.get(
                "hora",
                ""
            ),

            "Tema": noticia.get(
                "tema",
                ""
            ),

            "Palavras": noticia.get(
                "palavras_encontradas",
                ""
            ),

            "Titulo": noticia.get(
                "titulo",
                ""
            ),

            "Descrição": noticia.get(
                "descricao",
                ""
            ),

            "Categoria": noticia.get(
                "categoria",
                ""
            ),

            "Autor": noticia.get(
                "autor",
                ""
            ),

            "Publicado": noticia.get(
                "publicado",
                ""
            ),

            "Atualizado": noticia.get(
                "atualizado",
                ""
            ),

            "Imagem": noticia.get(
                "imagem",
                ""
            ),

            "Link": noticia.get(
                "link",
                ""
            )
        })

    # ------------------------------------------------------------
    # CRIAR JSON TEMPORARIO
    # ------------------------------------------------------------

    with open(
        caminho_json,
        "w",
        encoding="utf-8"
    ) as arquivo_json:

        json.dump(
            dados_para_json,
            arquivo_json,
            ensure_ascii=False,
            indent=4
        )

    # ------------------------------------------------------------
    # LER JSON TEMPORARIO
    # ------------------------------------------------------------

    with open(
        caminho_json,
        "r",
        encoding="utf-8"
    ) as arquivo_json:

        dados_json = json.load(
            arquivo_json
        )

    # ------------------------------------------------------------
    # CRIAR EXCEL
    # ------------------------------------------------------------

    workbook = Workbook()

    planilha = workbook.active
    planilha.title = "Planilha1"

    cabecalhos = [
        "Data",
        "Hora",
        "Tema",
        "Palavras",
        "Titulo",
        "Descrição",
        "Categoria",
        "Autor",
        "Publicado",
        "Atualizado",
        "Imagem",
        "Link"
    ]

    planilha.append(
        cabecalhos
    )

    for registro in dados_json:

        planilha.append([
            registro.get("Data", ""),
            registro.get("Hora", ""),
            registro.get("Tema", ""),
            registro.get("Palavras", ""),
            registro.get("Titulo", ""),
            registro.get("Descrição", ""),
            registro.get("Categoria", ""),
            registro.get("Autor", ""),
            registro.get("Publicado", ""),
            registro.get("Atualizado", ""),
            registro.get("Imagem", ""),
            registro.get("Link", "")
        ])

    # ------------------------------------------------------------
    # ESTILOS
    # ------------------------------------------------------------

    preenchimento_cabecalho = PatternFill(
        fill_type="solid",
        fgColor="B71C1C"
    )

    fonte_cabecalho = Font(
        name="Calibri",
        size=11,
        bold=True,
        color="FFFFFF"
    )

    alinhamento_cabecalho = Alignment(
        horizontal="center",
        vertical="center",
        wrap_text=True
    )

    borda_fina = Side(
        style="thin",
        color="D9D9D9"
    )

    borda = Border(
        left=borda_fina,
        right=borda_fina,
        top=borda_fina,
        bottom=borda_fina
    )

    # ------------------------------------------------------------
    # FORMATAR CABECALHO
    # Este bloco substitui a linha incorreta planilhacelula.fill.
    # ------------------------------------------------------------

    for linha_cabecalho in planilha.iter_rows(
        min_row=1,
        max_row=1,
        min_col=1,
        max_col=12
    ):

        for celula in linha_cabecalho:

            celula.fill = preenchimento_cabecalho
            celula.font = fonte_cabecalho
            celula.alignment = alinhamento_cabecalho
            celula.border = borda

    planilha.row_dimensions[1].height = 28

    ultima_linha = planilha.max_row

    # ------------------------------------------------------------
    # FORMATAR DADOS
    # ------------------------------------------------------------

    if ultima_linha >= 2:

        for linha in planilha.iter_rows(
            min_row=2,
            max_row=ultima_linha,
            min_col=1,
            max_col=12
        ):

            for celula in linha:

                celula.font = Font(
                    name="Calibri",
                    size=11
                )

                celula.alignment = Alignment(
                    vertical="top",
                    wrap_text=True
                )

                celula.border = borda

            numero_linha = linha[0].row

            planilha.row_dimensions[
                numero_linha
            ].height = 60

    # ------------------------------------------------------------
    # LARGURA DAS COLUNAS
    # ------------------------------------------------------------

    larguras = {
        "A": 13,
        "B": 11,
        "C": 30,
        "D": 35,
        "E": 55,
        "F": 70,
        "G": 22,
        "H": 30,
        "I": 20,
        "J": 20,
        "K": 55,
        "L": 55
    }

    for coluna, largura in larguras.items():

        planilha.column_dimensions[
            coluna
        ].width = largura

    # ------------------------------------------------------------
    # FORMATAR DATA E HORA COMO TEXTO
    # ------------------------------------------------------------

    if ultima_linha >= 2:

        for numero_linha in range(
            2,
            ultima_linha + 1
        ):

            planilha.cell(
                row=numero_linha,
                column=1
            ).number_format = "@"

            planilha.cell(
                row=numero_linha,
                column=2
            ).number_format = "@"

            planilha.cell(
                row=numero_linha,
                column=9
            ).number_format = "@"

            planilha.cell(
                row=numero_linha,
                column=10
            ).number_format = "@"

    # ------------------------------------------------------------
    # LINKS CLICAVEIS
    # ------------------------------------------------------------

    if ultima_linha >= 2:

        for numero_linha in range(
            2,
            ultima_linha + 1
        ):

            celula_imagem = planilha.cell(
                row=numero_linha,
                column=11
            )

            celula_link = planilha.cell(
                row=numero_linha,
                column=12
            )

            if (
                isinstance(
                    celula_imagem.value,
                    str
                )
                and celula_imagem.value.startswith(
                    ("http://", "https://")
                )
            ):

                celula_imagem.hyperlink = (
                    celula_imagem.value
                )

                celula_imagem.style = "Hyperlink"

                celula_imagem.alignment = Alignment(
                    vertical="top",
                    wrap_text=True
                )

                celula_imagem.border = borda

            if (
                isinstance(
                    celula_link.value,
                    str
                )
                and celula_link.value.startswith(
                    ("http://", "https://")
                )
            ):

                celula_link.hyperlink = (
                    celula_link.value
                )

                celula_link.style = "Hyperlink"

                celula_link.alignment = Alignment(
                    vertical="top",
                    wrap_text=True
                )

                celula_link.border = borda

    # ------------------------------------------------------------
    # TABELA, FILTRO E CONGELAMENTO
    # ------------------------------------------------------------

    planilha.freeze_panes = "A2"

    if ultima_linha >= 2:

        intervalo_tabela = (
            f"A1:L{ultima_linha}"
        )

        tabela = Table(
            displayName="TabelaNoticiasCNN",
            ref=intervalo_tabela
        )

        estilo_tabela = TableStyleInfo(
            name="TableStyleMedium2",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False
        )

        tabela.tableStyleInfo = estilo_tabela

        planilha.add_table(
            tabela
        )

    else:

        planilha.auto_filter.ref = "A1:L1"

    # ------------------------------------------------------------
    # CONFIGURACOES DA PLANILHA
    # ------------------------------------------------------------

    planilha.sheet_view.showGridLines = False

    planilha.page_setup.orientation = "landscape"
    planilha.page_setup.fitToWidth = 1
    planilha.page_setup.fitToHeight = 0

    planilha.print_title_rows = "1:1"

    planilha.sheet_properties.pageSetUpPr.fitToPage = True

    planilha.page_margins.left = 0.25
    planilha.page_margins.right = 0.25
    planilha.page_margins.top = 0.5
    planilha.page_margins.bottom = 0.5

    # ------------------------------------------------------------
    # SALVAR EXCEL
    # ------------------------------------------------------------

    workbook.save(
        caminho_excel
    )

    workbook.close()

    # ------------------------------------------------------------
    # REMOVER JSON TEMPORARIO
    # ------------------------------------------------------------

    try:

        if os.path.exists(
            caminho_json
        ):

            os.remove(
                caminho_json
            )

    except Exception as erro:

        print()
        print(
            "Nao foi possivel remover o JSON temporario."
        )

        print(erro)

    return caminho_excel


# ================================================================
# FUNCOES DO OUTLOOK
# ================================================================

def escapar_powershell(texto):

    return str(texto).replace(
        "'",
        "''"
    )


def enviar_email_outlook_html(
    destinatario,
    assunto,
    corpo_html,
    caminho_anexo
):

    caminho_anexo = os.path.abspath(
        caminho_anexo
    )

    if not os.path.isfile(
        caminho_anexo
    ):

        raise FileNotFoundError(
            "Arquivo Excel nao encontrado: "
            + caminho_anexo
        )

    destinatario_ps = escapar_powershell(
        destinatario
    )

    assunto_ps = escapar_powershell(
        assunto
    )

    anexo_ps = escapar_powershell(
        caminho_anexo
    )

    nome_temporario = (
        "cnn_corpo_email_"
        + datetime.now(
            FUSO_BRASIL
        ).strftime(
            "%Y%m%d_%H%M%S"
        )
        + ".html"
    )

    caminho_corpo = os.path.join(
        tempfile.gettempdir(),
        nome_temporario
    )

    with open(
        caminho_corpo,
        "w",
        encoding="utf-8-sig"
    ) as arquivo:

        arquivo.write(
            corpo_html
        )

    corpo_ps = escapar_powershell(
        caminho_corpo
    )

    script_powershell = f"""
$ErrorActionPreference = 'Stop'

$outlook = New-Object -ComObject Outlook.Application
$email = $outlook.CreateItem(0)

$email.To = '{destinatario_ps}'
$email.Subject = '{assunto_ps}'

$corpoHtml = Get-Content -LiteralPath '{corpo_ps}' -Raw -Encoding UTF8

$email.HTMLBody = $corpoHtml
$email.Attachments.Add('{anexo_ps}') | Out-Null

$email.Send()

Write-Output 'EMAIL_ENVIADO'
"""

    resultado = None

    try:

        resultado = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script_powershell
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120
        )

    finally:

        try:

            if os.path.exists(
                caminho_corpo
            ):

                os.remove(
                    caminho_corpo
                )

        except Exception:

            pass

    if resultado is None:

        raise RuntimeError(
            "O PowerShell nao foi executado."
        )

    if resultado.returncode != 0:

        mensagem_erro = (
            resultado.stderr.strip()
            or resultado.stdout.strip()
            or "Erro desconhecido durante o envio."
        )

        raise RuntimeError(
            mensagem_erro
        )

    if "EMAIL_ENVIADO" not in resultado.stdout:

        raise RuntimeError(
            "O Outlook nao confirmou o envio."
        )

    return True


# ================================================================
# BUSCA PRINCIPAL
# ================================================================

def buscar_noticias(
    data_desejada
):

    print()
    print("Consultando a CNN Brasil...")
    print("Aguarde...")

    xml = baixar_sitemap()

    if xml is None:

        print(
            "Nao foi possivel baixar o sitemap."
        )

        return False

    noticias_encontradas = extrair_noticias_da_data(
        xml,
        data_desejada
    )

    total = len(
        noticias_encontradas
    )

    print()
    print(
        "Noticias encontradas:",
        total
    )

    print()
    print(
        "Analisando materias e aplicando filtros..."
    )

    noticias_filtradas = []

    for numero, noticia in enumerate(
        noticias_encontradas,
        start=1
    ):

        print(
            f"Analisando noticia {numero} de {total}..."
        )

        detalhes = obter_detalhes_noticia(
            noticia["link"]
        )

        titulo = (
            detalhes["titulo"]
            or noticia["titulo"]
        )

        descricao = (
            detalhes["descricao"]
            or ""
        )

        conteudo = (
            detalhes["conteudo"]
            or ""
        )

        temas, palavras = classificar_noticia(
            titulo,
            descricao,
            conteudo
        )

        if not temas:

            time.sleep(0.3)
            continue

        if detalhes["publicado"]:

            publicado = formatar_data_iso(
                detalhes["publicado"]
            )

        else:

            publicado = (
                f"{noticia['data']} "
                f"{noticia['hora']}"
            )

        if detalhes["atualizado"]:

            atualizado = formatar_data_iso(
                detalhes["atualizado"]
            )

        else:

            atualizado = "Nao informado"

        noticias_filtradas.append({
            "data": noticia["data"],

            "hora": noticia["hora"],

            "tema": ", ".join(
                temas
            ),

            "palavras_encontradas": ", ".join(
                palavras
            ),

            "titulo": titulo,

            "descricao": (
                descricao
                or "Nao informado"
            ),

            "categoria": (
                detalhes["categoria"]
                or "Nao informado"
            ),

            "autor": (
                detalhes["autor"]
                or "Nao informado"
            ),

            "publicado": publicado,

            "atualizado": atualizado,

            "imagem": (
                detalhes["imagem"]
                or ""
            ),

            "link": noticia["link"]
        })

        time.sleep(0.3)

    print()
    print("=" * 80)
    print("RESULTADO")
    print("=" * 80)

    print(
        "Noticias analisadas:",
        total
    )

    print(
        "Noticias relevantes:",
        len(
            noticias_filtradas
        )
    )

    for numero, noticia in enumerate(
        noticias_filtradas,
        start=1
    ):

        print()
        print("-" * 80)
        print(f"NOTICIA {numero}")

        print(
            "Tema:",
            noticia["tema"]
        )

        print(
            "Palavras:",
            noticia["palavras_encontradas"]
        )

        print(
            "Titulo:",
            noticia["titulo"]
        )

        print(
            "Link:",
            noticia["link"]
        )

    # ------------------------------------------------------------
    # MONTAR HTML
    # ------------------------------------------------------------

    corpo_html = montar_corpo_email_html(
        data_desejada=data_desejada,
        total_analisadas=total,
        noticias_filtradas=noticias_filtradas
    )

    # ------------------------------------------------------------
    # CRIAR EXCEL
    # ------------------------------------------------------------

    try:

        print()
        print(
            "Criando arquivo Excel..."
        )

        arquivo_excel = criar_excel_noticias(
            noticias_filtradas=noticias_filtradas,
            data_desejada=data_desejada
        )

        print()
        print(
            "Arquivo Excel criado:",
            os.path.basename(
                arquivo_excel
            )
        )

    except Exception as erro:

        print()
        print("=" * 80)
        print("ERRO AO CRIAR O EXCEL")
        print("=" * 80)

        print()
        print(erro)

        return False

    # ------------------------------------------------------------
    # ENVIAR EMAIL
    # ------------------------------------------------------------

    try:

        print()
        print(
            "Enviando email HTML com Excel "
            "pelo Outlook classico..."
        )

        enviar_email_outlook_html(
            destinatario=DESTINATARIO_EMAIL,
            assunto=ASSUNTO_EMAIL,
            corpo_html=corpo_html,
            caminho_anexo=arquivo_excel
        )

        print()
        print("=" * 80)
        print("EMAIL ENVIADO COM SUCESSO")
        print("=" * 80)

        print(
            "Destinatario:",
            DESTINATARIO_EMAIL
        )

        print(
            "Assunto:",
            ASSUNTO_EMAIL
        )

        print(
            "Materias inseridas no corpo:",
            len(
                noticias_filtradas
            )
        )

        print(
            "Excel anexado:",
            os.path.basename(
                arquivo_excel
            )
        )

    except Exception as erro:

        print()
        print("=" * 80)
        print("ERRO NO ENVIO DO EMAIL")
        print("=" * 80)

        print()
        print(erro)

        print()
        print(
            "O arquivo Excel foi mantido para verificacao em:"
        )

        print(
            arquivo_excel
        )

        return False

    # ------------------------------------------------------------
    # REMOVER EXCEL DEPOIS DO ENVIO
    # ------------------------------------------------------------

    try:

        if os.path.exists(
            arquivo_excel
        ):

            os.remove(
                arquivo_excel
            )

            print()
            print(
                "Arquivo Excel temporario removido."
            )

    except Exception as erro:

        print()
        print(
            "O email foi enviado, mas o Excel "
            "temporario nao foi removido."
        )

        print(erro)

    return True


# ================================================================
# PROGRAMA PRINCIPAL
# ================================================================

def main():

    agora_brasil = datetime.now(
        FUSO_BRASIL
    )

    data_pesquisa = agora_brasil.strftime(
        "%d/%m/%Y"
    )

    print("=" * 80)
    print("MONITOR DE NOTICIAS - CNN BRASIL")
    print("=" * 80)

    print()
    print(
        "Data automatica:",
        data_pesquisa
    )

    print(
        "Horario:",
        agora_brasil.strftime(
            "%H:%M:%S"
        )
    )

    print(
        "Fuso horario: UTC-03:00"
    )

    print()
    print(
        "Destinatario:",
        DESTINATARIO_EMAIL
    )

    print(
        "Assunto:",
        ASSUNTO_EMAIL
    )

    print()
    print("Temas monitorados:")

    for tema, palavras in TEMAS.items():

        print()
        print(
            f"{tema}:"
        )

        print(
            ", ".join(
                palavras
            )
        )

    print()
    print("=" * 80)

    sucesso = buscar_noticias(
        data_pesquisa
    )

    if not sucesso:

        raise SystemExit(
            "O programa terminou com erro."
        )


if __name__ == "__main__":

    main()
