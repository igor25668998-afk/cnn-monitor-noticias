import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
import unicodedata
import json
import os
import time


# ================================================================
# CONFIGURACAO
# ================================================================

URL_CNN = "https://www.cnnbrasil.com.br/sitemap-news.xml"

# Horario de Brasilia - UTC-3
FUSO_BRASIL = timezone(
    timedelta(hours=-3)
)

# O arquivo sera sempre gravado neste mesmo local.
PASTA_RESULTADOS = "resultados"
NOME_ARQUIVO_JSON = "resultado_cnn.json"

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
# NORMALIZACAO
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


# ================================================================
# CLASSIFICACAO
# ================================================================

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

    return (
        temas_encontrados,
        palavras_encontradas
    )


# ================================================================
# META TAGS
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
# JSON-LD
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

        atributos = dict(
            attrs
        )

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
# HTTP
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

        print(
            "Erro HTTP:",
            erro.code,
            erro.reason
        )

    except urllib.error.URLError as erro:

        print(
            "Erro de conexao:",
            erro
        )

    except Exception as erro:

        print(
            "Erro inesperado:",
            erro
        )

    return None


# ================================================================
# AUXILIARES
# ================================================================

def obter_texto(elemento):

    if elemento is None:

        return ""

    return (
        elemento.text or ""
    ).strip()


def formatar_data_iso(
    data_iso
):

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


def obter_nome_autor(
    autor
):

    if isinstance(
        autor,
        str
    ):

        return autor.strip()

    if isinstance(
        autor,
        dict
    ):

        return str(
            autor.get(
                "name",
                ""
            )
        ).strip()

    if isinstance(
        autor,
        list
    ):

        nomes = []

        for pessoa in autor:

            if isinstance(
                pessoa,
                dict
            ):

                nome = str(
                    pessoa.get(
                        "name",
                        ""
                    )
                ).strip()

            elif isinstance(
                pessoa,
                str
            ):

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


def obter_url_imagem(
    imagem
):

    if isinstance(
        imagem,
        str
    ):

        return imagem.strip()

    if isinstance(
        imagem,
        dict
    ):

        return str(
            imagem.get(
                "url",
                ""
            )
        ).strip()

    if isinstance(
        imagem,
        list
    ) and imagem:

        primeira = imagem[0]

        if isinstance(
            primeira,
            str
        ):

            return primeira.strip()

        if isinstance(
            primeira,
            dict
        ):

            return str(
                primeira.get(
                    "url",
                    ""
                )
            ).strip()

    return ""


# ================================================================
# PROCURAR ARTIGO
# ================================================================

def procurar_artigo_json(
    dados
):

    if isinstance(
        dados,
        list
    ):

        for item in dados:

            artigo = procurar_artigo_json(
                item
            )

            if artigo:

                return artigo

        return None

    if not isinstance(
        dados,
        dict
    ):

        return None

    tipo = dados.get(
        "@type",
        ""
    )

    if isinstance(
        tipo,
        list
    ):

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

def obter_detalhes_noticia(
    url
):

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

        resultado[
            "erro"
        ] = str(
            erro
        )

        return resultado

    # META TAGS

    parser_meta = MetaParser()

    parser_meta.feed(
        html
    )

    metas = parser_meta.metadados

    resultado["titulo"] = (
        metas.get(
            "og:title",
            ""
        )
        or metas.get(
            "twitter:title",
            ""
        )
    )

    resultado["descricao"] = (
        metas.get(
            "og:description",
            ""
        )
        or metas.get(
            "description",
            ""
        )
        or metas.get(
            "twitter:description",
            ""
        )
    )

    resultado["categoria"] = metas.get(
        "article:section",
        ""
    )

    resultado["autor"] = (
        metas.get(
            "author",
            ""
        )
        or metas.get(
            "article:author",
            ""
        )
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
        metas.get(
            "og:image",
            ""
        )
        or metas.get(
            "twitter:image",
            ""
        )
    )

    # JSON-LD

    parser_json = JSONLDParser()

    parser_json.feed(
        html
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
            artigo.get(
                "headline"
            )
            or artigo.get(
                "name"
            )
            or resultado[
                "titulo"
            ]
        )

        resultado["descricao"] = (
            artigo.get(
                "description"
            )
            or resultado[
                "descricao"
            ]
        )

        resultado["categoria"] = (
            artigo.get(
                "articleSection"
            )
            or resultado[
                "categoria"
            ]
        )

        resultado["autor"] = (
            obter_nome_autor(
                artigo.get(
                    "author"
                )
            )
            or resultado[
                "autor"
            ]
        )

        resultado["publicado"] = (
            artigo.get(
                "datePublished"
            )
            or resultado[
                "publicado"
            ]
        )

        resultado["atualizado"] = (
            artigo.get(
                "dateModified"
            )
            or resultado[
                "atualizado"
            ]
        )

        resultado["conteudo"] = (
            artigo.get(
                "articleBody"
            )
            or resultado[
                "conteudo"
            ]
        )

        resultado["imagem"] = (
            obter_url_imagem(
                artigo.get(
                    "image"
                )
            )
            or resultado[
                "imagem"
            ]
        )

        break

    return resultado


# ================================================================
# NOTICIAS DA DATA
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
            "Erro ao interpretar sitemap:"
        )

        print(
            erro
        )

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

        noticias.append(
            {
                "titulo":
                    titulo,

                "data":
                    data_noticia,

                "hora":
                    data_hora.strftime(
                        "%H:%M"
                    ),

                "data_iso":
                    data_publicacao,

                "link":
                    link
            }
        )

    noticias.sort(
        key=lambda noticia: noticia[
            "data_iso"
        ],
        reverse=True
    )

    return noticias


# ================================================================
# CRIAR / SUBSTITUIR JSON
# ================================================================

def criar_arquivo_json(
    noticias,
    data_desejada,
    total_analisadas
):

    os.makedirs(
        PASTA_RESULTADOS,
        exist_ok=True
    )

    agora_brasil = datetime.now(
        FUSO_BRASIL
    )

    # Este caminho nunca muda.
    caminho = os.path.join(
        PASTA_RESULTADOS,
        NOME_ARQUIVO_JSON
    )

    dados_json = {

        "fonte":
            "CNN Brasil",

        "data_pesquisada":
            data_desejada,

        "data_geracao":
            agora_brasil.strftime(
                "%d/%m/%Y %H:%M:%S"
            ),

        "fuso_horario":
            "UTC-03:00",

        "total_analisadas":
            total_analisadas,

        "total_noticias":
            len(
                noticias
            ),

        "temas_monitorados":
            TEMAS,

        "noticias":
            noticias
    }

    # "w" substitui o arquivo existente.
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
# BUSCA
# ================================================================

def buscar_noticias(
    data_desejada
):

    print()
    print(
        "Consultando CNN Brasil..."
    )

    xml = baixar_sitemap()

    if xml is None:

        print(
            "Nao foi possivel baixar o sitemap."
        )

        return False

    noticias_encontradas = (
        extrair_noticias_da_data(
            xml,
            data_desejada
        )
    )

    total = len(
        noticias_encontradas
    )

    print(
        "Noticias encontradas:",
        total
    )

    noticias_filtradas = []

    for numero, noticia in enumerate(
        noticias_encontradas,
        start=1
    ):

        print(
            f"Analisando noticia "
            f"{numero} de {total}..."
        )

        detalhes = obter_detalhes_noticia(
            noticia[
                "link"
            ]
        )

        titulo = (
            detalhes[
                "titulo"
            ]
            or noticia[
                "titulo"
            ]
        )

        descricao = (
            detalhes[
                "descricao"
            ]
            or ""
        )

        conteudo = (
            detalhes[
                "conteudo"
            ]
            or ""
        )

        temas, palavras = classificar_noticia(
            titulo,
            descricao,
            conteudo
        )

        if not temas:

            time.sleep(
                0.3
            )

            continue

        if detalhes[
            "publicado"
        ]:

            publicado = formatar_data_iso(
                detalhes[
                    "publicado"
                ]
            )

        else:

            publicado = (
                f"{noticia['data']} "
                f"{noticia['hora']}"
            )

        if detalhes[
            "atualizado"
        ]:

            atualizado = formatar_data_iso(
                detalhes[
                    "atualizado"
                ]
            )

        else:

            atualizado = (
                "Nao informado"
            )

        noticia_final = {

            "data":
                noticia[
                    "data"
                ],

            "hora":
                noticia[
                    "hora"
                ],

            "tema":
                ", ".join(
                    temas
                ),

            "palavras_encontradas":
                ", ".join(
                    palavras
                ),

            "titulo":
                titulo,

            "descricao":
                descricao
                or "Nao informado",

            "categoria":
                detalhes[
                    "categoria"
                ]
                or "Nao informado",

            "autor":
                detalhes[
                    "autor"
                ]
                or "Nao informado",

            "publicado":
                publicado,

            "atualizado":
                atualizado,

            "imagem":
                detalhes[
                    "imagem"
                ],

            "link":
                noticia[
                    "link"
                ]
        }

        noticias_filtradas.append(
            noticia_final
        )

        time.sleep(
            0.3
        )

    print()
    print(
        "=" * 80
    )

    print(
        "RESULTADO"
    )

    print(
        "=" * 80
    )

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

    arquivo_json = criar_arquivo_json(
        noticias=noticias_filtradas,
        data_desejada=data_desejada,
        total_analisadas=total
    )

    print()
    print(
        "=" * 80
    )

    print(
        "JSON ATUALIZADO"
    )

    print(
        "=" * 80
    )

    print(
        "Arquivo:",
        arquivo_json
    )

    print(
        "Este arquivo substitui "
        "automaticamente o anterior."
    )

    return True


# ================================================================
# MAIN
# ================================================================

def main():

    agora_brasil = datetime.now(
        FUSO_BRASIL
    )

    data_pesquisa = agora_brasil.strftime(
        "%d/%m/%Y"
    )

    print(
        "=" * 80
    )

    print(
        "MONITOR DE NOTICIAS - CNN BRASIL"
    )

    print(
        "=" * 80
    )

    print(
        "Data:",
        data_pesquisa
    )

    print(
        "Horario:",
        agora_brasil.strftime(
            "%H:%M:%S"
        )
    )

    print(
        "Fuso: UTC-03:00"
    )

    print(
        "Arquivo de saida:",
        (
            f"{PASTA_RESULTADOS}/"
            f"{NOME_ARQUIVO_JSON}"
        )
    )

    print(
        "=" * 80
    )

    sucesso = buscar_noticias(
        data_pesquisa
    )

    if not sucesso:

        raise SystemExit(
            "O programa terminou com erro."
        )


if __name__ == "__main__":

    main()
