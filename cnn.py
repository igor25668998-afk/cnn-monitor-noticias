import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from html.parser import HTMLParser
import unicodedata
import subprocess
import tempfile
import json
import os
import time


# ================================================================
# CONFIGURACAO
# ================================================================

URL_CNN = "https://www.cnnbrasil.com.br/sitemap-news.xml"

DESTINATARIO_EMAIL = "igor.franca@fedex.com"

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

        palavras_do_tema = []

        for palavra in palavras:

            palavra_normalizada = normalizar_texto(
                palavra
            )

            if palavra_normalizada in texto_completo:

                if palavra not in palavras_encontradas:
                    palavras_encontradas.append(
                        palavra
                    )

                palavras_do_tema.append(
                    palavra
                )

        if palavras_do_tema:
            temas_encontrados.append(
                tema
            )

    return (
        temas_encontrados,
        palavras_encontradas
    )


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

        print("\nErro HTTP ao acessar a CNN.")
        print("Codigo:", erro.code)
        print("Motivo:", erro.reason)

    except urllib.error.URLError as erro:

        print("\nErro de conexao ao acessar a CNN.")
        print(erro)

    except Exception as erro:

        print("\nErro inesperado ao acessar a CNN.")
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
                nomes.append(nome)

        return ", ".join(nomes)

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

        primeira = imagem[0]

        if isinstance(primeira, str):
            return primeira.strip()

        if isinstance(primeira, dict):

            return str(
                primeira.get(
                    "url",
                    ""
                )
            ).strip()

    return ""


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
# DETALHES DA NOTICIA
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

        html = dados_html.decode(
            "utf-8",
            errors="ignore"
        )

    except Exception as erro:

        resultado["erro"] = str(
            erro
        )

        return resultado

    # Meta tags

    parser_meta = MetaParser()
    parser_meta.feed(html)

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

    # JSON-LD

    parser_json = JSONLDParser()
    parser_json.feed(html)

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

        print(
            "\nErro ao interpretar o sitemap:"
        )

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

        except ValueError:
            continue

        data_noticia = data_hora.strftime(
            "%d/%m/%Y"
        )

        if data_noticia != data_desejada:
            continue

        noticias.append({
            "titulo": titulo,
            "data": data_noticia,
            "hora": data_hora.strftime(
                "%H:%M"
            ),
            "data_iso": data_publicacao,
            "link": link
        })

    noticias.sort(
        key=lambda noticia: noticia[
            "data_iso"
        ],
        reverse=True
    )

    return noticias


# ================================================================
# CRIAR JSON TEMPORARIO
# ================================================================

def criar_json_temporario(
    noticias,
    data_desejada
):

    data_arquivo = datetime.strptime(
        data_desejada,
        "%d/%m/%Y"
    ).strftime(
        "%Y-%m-%d"
    )

    nome_arquivo = (
        f"cnn_resultado_{data_arquivo}.json"
    )

    caminho = os.path.join(
        tempfile.gettempdir(),
        nome_arquivo
    )

    dados_json = {
        "fonte": "CNN Brasil",
        "data_pesquisada": data_desejada,
        "data_geracao": datetime.now().strftime(
            "%d/%m/%Y %H:%M:%S"
        ),
        "total_noticias": len(noticias),
        "temas_monitorados": TEMAS,
        "noticias": noticias
    }

    with open(
        caminho,
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            dados_json,
            arquivo,
            ensure_ascii=False,
            indent=4
        )

    return caminho


# ================================================================
# ENVIAR EMAIL PELO OUTLOOK CLASSICO
# ================================================================

def escapar_powershell(texto):

    return str(texto).replace(
        "'",
        "''"
    )


def enviar_email_outlook(
    destinatario,
    assunto,
    corpo,
    caminho_anexo
):

    caminho_anexo = os.path.abspath(
        caminho_anexo
    )

    if not os.path.isfile(
        caminho_anexo
    ):

        raise FileNotFoundError(
            f"Arquivo de anexo nao encontrado: "
            f"{caminho_anexo}"
        )

    destinatario_ps = escapar_powershell(
        destinatario
    )

    assunto_ps = escapar_powershell(
        assunto
    )

    corpo_ps = escapar_powershell(
        corpo
    )

    anexo_ps = escapar_powershell(
        caminho_anexo
    )

    script_powershell = f"""
$ErrorActionPreference = 'Stop'

$outlook = New-Object -ComObject Outlook.Application
$email = $outlook.CreateItem(0)

$email.To = '{destinatario_ps}'
$email.Subject = '{assunto_ps}'
$email.Body = '{corpo_ps}'

$email.Attachments.Add('{anexo_ps}') | Out-Null

$email.Send()

Write-Output 'EMAIL_ENVIADO'
"""

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
        timeout=90
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
            "O Outlook nao confirmou o envio do email."
        )

    return True


# ================================================================
# MONTAR CORPO DO EMAIL
# ================================================================

def montar_corpo_email(
    data_desejada,
    total_analisadas,
    noticias_filtradas
):

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

    linhas = [
        "Bom dia,",
        "",
        "Segue o resultado da consulta automatica realizada "
        "no portal CNN Brasil.",
        "",
        f"Data pesquisada: {data_desejada}",
        f"Noticias encontradas no sitemap: {total_analisadas}",
        (
            "Noticias relevantes apos a aplicacao dos filtros: "
            f"{len(noticias_filtradas)}"
        ),
        "",
        "Resumo por tema:"
    ]

    for tema, quantidade in contagem_temas.items():

        linhas.append(
            f"- {tema}: {quantidade}"
        )

    linhas.extend([
        "",
        "O resultado detalhado, incluindo os titulos, descricoes, "
        "categorias, autores, datas, imagens e links das materias, "
        "esta disponivel no arquivo JSON em anexo.",
        "",
        "Mensagem gerada automaticamente pelo Monitor de Noticias CNN."
    ])

    return "\n".join(
        linhas
    )


# ================================================================
# EXECUTAR BUSCA
# ================================================================

def buscar_noticias(data_desejada):

    print(
        "\nConsultando a CNN Brasil..."
    )

    print(
        "Aguarde...\n"
    )

    xml = baixar_sitemap()

    if xml is None:

        print(
            "Nao foi possivel baixar o sitemap."
        )

        return

    noticias_encontradas = extrair_noticias_da_data(
        xml,
        data_desejada
    )

    if not noticias_encontradas:

        print(
            "\nNenhuma noticia foi encontrada para essa data."
        )

        return

    total = len(
        noticias_encontradas
    )

    print(
        "Noticias encontradas:",
        total
    )

    print(
        "\nAnalisando materias e aplicando os filtros...\n"
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

            time.sleep(0.5)
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
            "tema": ", ".join(temas),
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
            "imagem": detalhes["imagem"],
            "link": noticia["link"]
        })

        time.sleep(0.5)

    print("\n" + "=" * 80)
    print("RESULTADO")
    print("=" * 80)

    print(
        "\nNoticias analisadas:",
        total
    )

    print(
        "Noticias relevantes:",
        len(noticias_filtradas)
    )

    if not noticias_filtradas:

        print(
            "\nNenhuma noticia continha as "
            "palavras-chave configuradas."
        )

        return

    for numero, noticia in enumerate(
        noticias_filtradas,
        start=1
    ):

        print("\n" + "-" * 80)
        print(f"NOTICIA {numero}")
        print("Tema:", noticia["tema"])

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

    # Criar JSON temporario

    arquivo_json = criar_json_temporario(
        noticias_filtradas,
        data_desejada
    )

    assunto = (
        f"[CNN] Resultados da consulta de noticias "
        f"- {data_desejada}"
    )

    corpo = montar_corpo_email(
        data_desejada=data_desejada,
        total_analisadas=total,
        noticias_filtradas=noticias_filtradas
    )

    try:

        print(
            "\nEnviando email pelo Outlook..."
        )

        enviar_email_outlook(
            destinatario=DESTINATARIO_EMAIL,
            assunto=assunto,
            corpo=corpo,
            caminho_anexo=arquivo_json
        )

        print("\n" + "=" * 80)
        print("EMAIL ENVIADO COM SUCESSO")
        print("=" * 80)

        print(
            "\nDestinatario:",
            DESTINATARIO_EMAIL
        )

        print(
            "Assunto:",
            assunto
        )

        print(
            "Anexo:",
            os.path.basename(
                arquivo_json
            )
        )

    except Exception as erro:

        print("\n" + "=" * 80)
        print("ERRO NO ENVIO DO EMAIL")
        print("=" * 80)

        print(
            "\nErro:",
            erro
        )

        print(
            "\nO JSON foi mantido temporariamente em:"
        )

        print(
            arquivo_json
        )

        return

    # Apagar JSON depois do envio

    try:

        if os.path.exists(
            arquivo_json
        ):

            os.remove(
                arquivo_json
            )

            print(
                "\nArquivo JSON temporario removido."
            )

    except Exception as erro:

        print(
            "\nO email foi enviado, mas o arquivo "
            "temporario nao foi removido."
        )

        print(
            "Erro:",
            erro
        )


# ================================================================
# VALIDAR DATA
# ================================================================

def validar_data(data):

    try:

        datetime.strptime(
            data,
            "%d/%m/%Y"
        )

        return True

    except ValueError:
        return False


# ================================================================
# PROGRAMA PRINCIPAL
# ================================================================

print("=" * 80)
print("MONITOR DE NOTICIAS - CNN BRASIL")
print("=" * 80)

print("\nTemas monitorados:")

for tema, palavras in TEMAS.items():

    print(
        f"\n{tema}:"
    )

    print(
        ", ".join(palavras)
    )

print("\n" + "=" * 80)

data_pesquisa = input(
    "\nDigite a data desejada "
    "(DD/MM/AAAA): "
).strip()

if not validar_data(
    data_pesquisa
):

    print("\nData invalida.")
    print("Use o formato DD/MM/AAAA.")

else:

    buscar_noticias(
        data_pesquisa
    )