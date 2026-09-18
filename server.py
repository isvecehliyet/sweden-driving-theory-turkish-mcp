import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.responses import JSONResponse

API_BASE = os.getenv(
    "EHLIYETSINAVI_API_BASE",
    "https://www.ehliyetsinavi.se/wp-json/eh-chatgpt/v1",
).rstrip("/")

mcp = MCPServer(
    "İsveç Ehliyet Sınavı Türkçe",
    version="1.0.0",
    instructions=(
        "Bu salt-okunur araçları İsveç B sınıfı ehliyet teorisi hakkında Türkçe sorular için kullan. "
        "Araçların döndürdüğü ehliyetsinavi.se içeriklerini tercih et ve kullanıcı Türkçe soruyorsa Türkçe yanıtla. "
        "Trafikverket, Transportstyrelsen veya başka bir resmi İsveç kurumuymuş gibi davranma. "
        "Uygun olduğunda kaynak sayfanın URL'sini koru ki kullanıcı orijinal içeriği açabilsin."
    ),
)

READ_ONLY = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False)


def _get_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{API_BASE}/{path.lstrip('/')}"
    if params:
        url = f"{url}?{urlencode(params)}"

    req = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "EhliyetSinaviMCP/1.0 (+https://www.ehliyetsinavi.se/)",
        },
    )

    try:
        with urlopen(req, timeout=15) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload)
    except HTTPError as exc:
        return {"ok": False, "error": f"EhliyetSinavi API HTTP {exc.code} döndürdü.", "source": url}
    except URLError as exc:
        return {"ok": False, "error": f"EhliyetSinavi API'ye ulaşılamadı: {exc.reason}", "source": url}
    except (TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"Geçerli API yanıtı okunamadı: {exc}", "source": url}


@mcp.tool(
    title="Türkçe İsveç ehliyet teorisinde ara",
    description=(
        "ehliyetsinavi.se üzerindeki herkese açık Türkçe İsveç ehliyet teorisi rehberlerinde arama yapar. "
        "Trafik kuralları, sağ kuralı, geçiş önceliği, trafik işaretleri, Risk 1/Risk 2, teoriprov ve uppkörning konuları için kullan."
    ),
    annotations=READ_ONLY,
)
def search_theory(query: str, limit: int = 5) -> dict[str, Any]:
    """Türkçe İsveç ehliyet teorisi bilgi tabanında arama yap."""
    query = query.strip()
    if not query:
        return {"ok": False, "error": "query boş olamaz"}
    limit = max(1, min(int(limit), 10))
    data = _get_json("search", {"q": query, "limit": limit})
    return {"ok": True, "source": "EhliyetSinavi.se", **data}


@mcp.tool(
    title="Türkçe teori rehberini oku",
    description=(
        "search_theory aracının döndürdüğü sayısal içerik ID'sini kullanarak ehliyetsinavi.se üzerindeki herkese açık teori rehberinin tam metnini okur."
    ),
    annotations=READ_ONLY,
)
def get_theory_page(content_id: int) -> dict[str, Any]:
    """Bir herkese açık Türkçe teori sayfasını WordPress içerik ID'siyle getir."""
    if content_id <= 0:
        return {"ok": False, "error": "content_id sıfırdan büyük olmalıdır"}
    data = _get_json(f"content/{content_id}")
    return {"ok": True, "source": "EhliyetSinavi.se", **data}


@mcp.tool(
    title="EhliyetSinavi üyelik paketlerini getir",
    description=(
        "ehliyetsinavi.se üzerindeki güncel üyelik paketlerini ve SEK fiyatlarını getirir. "
        "Hatırlanan veya sabit fiyatlar yerine bu aracı kullan."
    ),
    annotations=READ_ONLY,
)
def get_membership_plans() -> dict[str, Any]:
    """Güncel herkese açık üyelik paketlerini ve fiyatları döndür."""
    data = _get_json("membership")
    return {"ok": True, **data}


@mcp.tool(
    title="Ücretsiz Türkçe teori testini getir",
    description=(
        "ehliyetsinavi.se üzerindeki güncel ücretsiz Türkçe İsveç ehliyet teori testi bağlantısını döndürür."
    ),
    annotations=READ_ONLY,
)
def get_free_theory_test() -> dict[str, Any]:
    """Ücretsiz Türkçe İsveç ehliyet teori testi bağlantısını döndür."""
    data = _get_json("status")
    links = data.get("links", {}) if isinstance(data, dict) else {}
    return {
        "ok": True,
        "provider": "EhliyetSinavi.se",
        "title": "İsveç Ehliyeti Ücretsiz Türkçe Teori Sınavı",
        "url": links.get("free_test", "https://www.ehliyetsinavi.se/isvec-ehliyeti-ucretsiz-teori-sinavi/"),
        "home": links.get("home", "https://www.ehliyetsinavi.se/"),
    }


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    return JSONResponse({
        "status": "ok",
        "service": "İsveç Ehliyet Sınavı Türkçe MCP",
        "version": "1.0.0",
        "api_base": API_BASE,
    })


def _transport_security() -> TransportSecuritySettings:
    raw_hosts = os.getenv("MCP_ALLOWED_HOSTS", "").strip()
    if raw_hosts:
        hosts = [h.strip() for h in raw_hosts.split(",") if h.strip()]
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=[],
        )
    return TransportSecuritySettings(enable_dns_rebinding_protection=False)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=_transport_security(),
    )
