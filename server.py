
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.responses import JSONResponse, PlainTextResponse


# ====================================================
# GENEL AYARLAR
# ====================================================

API_BASE = os.getenv(
    "EHLIYETSINAVI_API_BASE",
    "https://www.ehliyetsinavi.se/wp-json/eh-chatgpt/v1",
).rstrip("/")

SERVER_VERSION = "1.0.3"

# OpenAI geliştirici panelindeki mevcut alan adı doğrulama tokenı.
# Panel yeni token üretirse bu değeri değiştirin.
OPENAI_VERIFICATION_TOKEN = (
    "P-eCBI80FasLeaJKy_fuVmNXFJz9-Puvkr35S33WkII"
)


# ====================================================
# MCP SUNUCUSU
# ====================================================

mcp = MCPServer(
    "İsveç Ehliyet Sınavı Türkçe",
    version=SERVER_VERSION,
    instructions=(
        "Bu salt-okunur araçları İsveç B sınıfı ehliyet teorisi hakkında "
        "Türkçe sorular için kullan. Araçların döndürdüğü ehliyetsinavi.se "
        "içeriklerini tercih et ve kullanıcı Türkçe soruyorsa Türkçe yanıtla. "
        "Trafikverket, Transportstyrelsen veya başka bir resmî İsveç kurumuymuş "
        "gibi davranma. Uygun olduğunda kaynak sayfanın URL'sini paylaş. "
        "Yalnızca herkese açık eğitim içeriklerini kullan. Ücretli üyelik "
        "paketlerini veya fiyatlarını listeleme; satın alma ya da abonelik "
        "yükseltme işlemi yapma."
    ),
)


# ====================================================
# MCP ARAÇ GÜVENLİK TANIMLARI
# ====================================================

READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    open_world_hint=True,
    idempotent_hint=True,
)


# ====================================================
# WORDPRESS API BAĞLANTISI
# ====================================================

def _get_json(
    path: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:

    url = f"{API_BASE}/{path.lstrip('/')}"

    if params:
        url = f"{url}?{urlencode(params)}"

    req = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": (
                f"EhliyetSinaviMCP/{SERVER_VERSION} "
                "(+https://www.ehliyetsinavi.se/)"
            ),
        },
    )

    try:
        with urlopen(req, timeout=15) as response:
            payload = response.read().decode("utf-8")

        data = json.loads(payload)

        if not isinstance(data, dict):
            return {
                "ok": False,
                "error": "API yanıtı beklenen JSON nesnesi biçiminde değil.",
                "source": url,
            }

        return data

    except HTTPError as exc:
        return {
            "ok": False,
            "error": f"EhliyetSinavi API HTTP {exc.code} döndürdü.",
            "source": url,
        }

    except URLError as exc:
        return {
            "ok": False,
            "error": f"EhliyetSinavi API'ye ulaşılamadı: {exc.reason}",
            "source": url,
        }

    except (TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {
            "ok": False,
            "error": f"Geçerli API yanıtı okunamadı: {exc}",
            "source": url,
        }


# ====================================================
# ARAÇ 1 — TÜRKÇE TEORİ İÇERİKLERİNDE ARAMA
# ====================================================

@mcp.tool(
    title="Türkçe İsveç ehliyet teorisinde ara",
    description=(
        "ehliyetsinavi.se üzerindeki herkese açık Türkçe İsveç ehliyet teorisi "
        "rehberlerinde arama yapar. Trafik kuralları, sağ kuralı, geçiş "
        "önceliği, trafik işaretleri, Risk 1/Risk 2, teoriprov ve uppkörning "
        "konuları için kullan. Yalnızca dış kaynaktan okuma yapar."
    ),
    annotations=READ_ONLY,
)
def search_theory(query: str, limit: int = 5) -> dict[str, Any]:
    """Herkese açık Türkçe İsveç ehliyet teorisi rehberlerinde ara."""

    query = query.strip()

    if not query:
        return {
            "ok": False,
            "error": "query boş olamaz",
        }

    limit = max(1, min(int(limit), 10))

    data = _get_json(
        "search",
        {
            "q": query,
            "limit": limit,
        },
    )

    return {
        "source": "EhliyetSinavi.se",
        **data,
    }


# ====================================================
# ARAÇ 2 — TÜRKÇE TEORİ REHBERİNİ OKU
# ====================================================

@mcp.tool(
    title="Türkçe teori rehberini oku",
    description=(
        "search_theory aracının döndürdüğü sayısal içerik ID'siyle "
        "ehliyetsinavi.se üzerindeki herkese açık teori rehberinin metnini "
        "okur. Hesap veya ücretli içerik erişimi sağlamaz."
    ),
    annotations=READ_ONLY,
)
def get_theory_page(content_id: int) -> dict[str, Any]:
    """Herkese açık Türkçe teori rehberini WordPress içerik ID'siyle getir."""

    if content_id <= 0:
        return {
            "ok": False,
            "error": "content_id sıfırdan büyük olmalıdır",
        }

    data = _get_json(f"content/{content_id}")

    return {
        "source": "EhliyetSinavi.se",
        **data,
    }


# ====================================================
# ARAÇ 3 — ÜCRETSİZ TÜRKÇE TEORİ TESTİ
# ====================================================

@mcp.tool(
    title="Ücretsiz Türkçe teori testini getir",
    description=(
        "ehliyetsinavi.se üzerindeki ücretsiz Türkçe İsveç ehliyet teori "
        "testinin herkese açık bağlantısını döndürür. Satın alma işlemi yapmaz."
    ),
    annotations=READ_ONLY,
)
def get_free_theory_test() -> dict[str, Any]:
    """Ücretsiz Türkçe ehliyet teori testi bağlantısını getir."""

    data = _get_json("status")

    links = data.get("links", {})

    if not isinstance(links, dict):
        links = {}

    return {
        "ok": True,
        "provider": "EhliyetSinavi.se",
        "title": "İsveç Ehliyeti Ücretsiz Türkçe Teori Sınavı",
        "url": links.get(
            "free_test",
            "https://www.ehliyetsinavi.se/isvec-ehliyeti-ucretsiz-teori-sinavi/",
        ),
        "home": links.get(
            "home",
            "https://www.ehliyetsinavi.se/",
        ),
    }


# ====================================================
# OPENAI ALAN ADI DOĞRULAMASI
# ====================================================

@mcp.custom_route(
    "/.well-known/openai-apps-challenge",
    methods=["GET"],
)
async def openai_domain_verification(_request):
    """OpenAI alan adı doğrulama isteğine düz metin olarak yanıt ver."""

    return PlainTextResponse(
        content=OPENAI_VERIFICATION_TOKEN,
        status_code=200,
    )


# ====================================================
# SUNUCU SAĞLIK KONTROLÜ
# ====================================================

@mcp.custom_route("/health", methods=["GET"])
async def health(_request):

    return JSONResponse({
        "status": "ok",
        "service": "İsveç Ehliyet Sınavı Türkçe MCP",
        "version": SERVER_VERSION,
        "api_base": API_BASE,
    })


# ====================================================
# MCP TRANSPORT GÜVENLİĞİ
# ====================================================

def _transport_security() -> TransportSecuritySettings:

    raw_hosts = os.getenv(
        "MCP_ALLOWED_HOSTS",
        "",
    ).strip()

    if raw_hosts:
        hosts = [
            h.strip()
            for h in raw_hosts.split(",")
            if h.strip()
        ]

        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=[],
        )

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    )


# ====================================================
# RENDER SUNUCUSUNU BAŞLAT
# ====================================================

if __name__ == "__main__":

    port = int(
        os.getenv("PORT", "8000")
    )

    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=_transport_security(),
    )
