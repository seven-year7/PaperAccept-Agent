"""
/**
 * @Module: scripts/test_elasticsearch_connection.py
 * @Description: 从项目根 .env 读取 ELASTICSEARCH_URL、Basic Auth、TLS（CA/指纹/verify）并测验 ES 连通性。
 * @Interface: python scripts/test_elasticsearch_connection.py
 *            python scripts/test_elasticsearch_connection.py --print-fingerprint  # 仅打印服务端证书 SHA256 指纹写入 .env
 */
"""

from __future__ import annotations

import hashlib
import socket
import ssl
import sys
from pathlib import Path
from urllib.parse import urlparse

# 项目根加入 path，便于加载 app.config（与 uvicorn 一致读取 .env）
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _host_port_from_elasticsearch_url(url: str) -> tuple[str, int]:
    u = urlparse((url or "").strip())
    host = u.hostname or "localhost"
    if u.port is not None:
        port = u.port
    else:
        port = 443 if (u.scheme or "").lower() == "https" else 9200
    return host, port


def print_fingerprint_main() -> int:
    """不校验 TLS，拉取当前服务端证书并打印 ELASTICSEARCH_SSL_ASSERT_FINGERPRINT=（ES 换证后重跑更新 .env）。"""
    from app.config import config

    url = (config.elasticsearch_url or "").strip()
    if not url:
        print("[ERROR] ELASTICSEARCH_URL 未配置。")
        return 1
    host, port = _host_port_from_elasticsearch_url(url)
    ctx = ssl._create_unverified_context()
    try:
        with socket.create_connection((host, port), timeout=15) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                der = ssock.getpeercert(binary_form=True)
    except OSError as e:
        print(f"[ERROR] 无法连接 {host}:{port} — {e}")
        return 2
    if not der:
        print("[ERROR] 服务端未返回 TLS 证书（der 为空）。")
        return 2
    fp = hashlib.sha256(der).hexdigest()
    colon = ":".join(fp[i : i + 2].upper() for i in range(0, len(fp), 2))
    print(f"# 将下行写入 .env（TLS 校验保持开启）")
    print(f"ELASTICSEARCH_SSL_ASSERT_FINGERPRINT={colon}")
    return 0


def main() -> int:
    # @Step: 1 - 加载配置（含 ELASTICSEARCH_BASIC_AUTH_*）
    from app.config import config
    from app.services.elasticsearch_chunk_store import elasticsearch_chunk_store

    url = (config.elasticsearch_url or "").strip()
    user = (config.elasticsearch_basic_auth_user or "").strip()
    has_password = bool((config.elasticsearch_basic_auth_password or "").strip())
    ca = (config.elasticsearch_ca_certs or "").strip()
    fp = (config.elasticsearch_ssl_assert_fingerprint or "").strip()

    print("== Elasticsearch Connection Self-Test ==")
    print(f"elasticsearch_url={url or '(empty)'}")
    print(f"basic_auth_user={'(set)' if user else '(empty)'} user_len={len(user)}")
    print(f"basic_auth_password={'(set)' if has_password else '(empty)'}")
    print(f"elasticsearch_verify_certs={config.elasticsearch_verify_certs}")
    print(f"elasticsearch_ca_certs={ca or '(empty)'}")
    print(f"elasticsearch_ssl_assert_fingerprint={'(set)' if fp else '(empty)'}")
    print(f"elasticsearch_index={config.elasticsearch_index}")
    print(f"rag_hybrid_enabled={config.rag_hybrid_enabled} (本脚本不依赖此项)")
    print()

    if not url:
        print("[ERROR] ELASTICSEARCH_URL 未配置，请在 .env 中设置。")
        return 1

    if user and not has_password:
        print("[WARN] 已配置 ELASTICSEARCH_BASIC_AUTH_USER 但未配置密码，可能认证失败。")
        print()

    # @Step: 2 - 构建客户端（与 elasticsearch_chunk_store._build_client 逻辑一致）
    cli = elasticsearch_chunk_store.diagnostic_client()
    if cli is None:
        print("[ERROR] 无法构建 Elasticsearch 客户端。")
        return 1

    # @Step: 3 - ping + cluster info + 目标索引是否存在
    try:
        ok = bool(cli.ping())
        print(f"ping={ok}")
        if not ok:
            print("[ERROR] ping 返回 False；尝试 cluster.health() 以获取详细错误…")
            try:
                cli.cluster.health()
            except Exception as e2:
                print(f"  detail={type(e2).__name__}: {e2}")
            return 2

        info = cli.info()
        name = (info.get("cluster_name") or info.get("cluster_uuid") or "?")
        ver = (info.get("version") or {}).get("number", "?")
        print(f"cluster_name={name}")
        print(f"version={ver}")

        idx = config.elasticsearch_index
        exists = cli.indices.exists(index=idx)
        print(f"index_exists[{idx}]={exists}")
        if exists:
            try:
                stats = cli.indices.stats(index=idx, metric=["docs"])
                total = (
                    stats.get("indices", {})
                    .get(idx, {})
                    .get("primaries", {})
                    .get("docs", {})
                    .get("count")
                )
                print(f"index_docs_count(approx)={total}")
            except Exception as stat_e:
                print(f"[WARN] 读取索引统计失败: {stat_e}")

        print()
        print("[OK] Elasticsearch 连通性正常（TLS + Basic Auth 与线上一致）。")
        return 0

    except Exception as e:
        print("[ERROR] 请求 Elasticsearch 失败：")
        print(f"  type={type(e).__name__}")
        print(f"  err={e}")
        print()
        print("排查建议：")
        print("- 核对 ELASTICSEARCH_URL 协议/主机/端口")
        print("- 核对 ELASTICSEARCH_BASIC_AUTH_USER / ELASTICSEARCH_BASIC_AUTH_PASSWORD")
        print("- HTTPS 自签名：优先 ELASTICSEARCH_CA_CERTS（完整 CA 链）；若报 key usage 等错误，运行:")
        print("    python scripts/test_elasticsearch_connection.py --print-fingerprint")
        print("  将输出的 ELASTICSEARCH_SSL_ASSERT_FINGERPRINT 写入 .env")
        print("- 临时排障（不推荐生产）：ELASTICSEARCH_VERIFY_CERTS=false")
        return 3


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--print-fingerprint", "-f"):
        raise SystemExit(print_fingerprint_main())
    raise SystemExit(main())
