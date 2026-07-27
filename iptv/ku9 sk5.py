import requests
import urllib.parse
from typing import Tuple, Any, Dict, Union, Iterable
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import socket
import sys
from base.parser import Parser as BaseParser

# --- 【关键补丁函数】过滤掉 IPv6 地址 ---
original_getaddrinfo = socket.getaddrinfo

def getaddrinfo_ipv4_only(*args):
    try:
        res = original_getaddrinfo(*args)
        ipv4_res = [r for r in res if r[0] == socket.AF_INET]
        if not ipv4_res and res:
            if res[0][0] == socket.AF_INET6:
                return []
            return res
        return ipv4_res
    except Exception:
        raise

# ----------------------------------------------

class Parser(BaseParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self, 'address'):
            self.address = "http://default.proxy.host/path"
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        s = requests.Session()
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.1,
            status_forcelist=[408, 500, 502, 503, 504, 599]
        )
        adapter = HTTPAdapter(
            pool_connections=20,
            pool_maxsize=50,
            max_retries=retry_strategy
        )
        s.mount('http://', adapter)
        s.mount('https://', adapter)
        s.headers.update({
            'Accept': '*/*',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive',
            'User-Agent': 'okhttp/3.15',
        })
        return s

    def _get_proxy(self, ip: str) -> Dict[str, str]:
        if ip:
            return {
                "http": f"socks5://{ip}",
                "https": f"socks5://{ip}"
            }
        return {}

    def parse(self, params: Dict[str, str], raw_query_string: str = None) -> Dict[str, str]:
        """
        仅处理参数构建 URL，移除状态预检查以加快响应速度。
        """
        ip = params.get('ip', '').strip()
        base_url = params.get('u', '').strip()
        
        if not ip: return {"error": "缺少代理IP参数: ip"}
        if not base_url: return {"error": "缺少播放URL参数: u"}
            
        try:
            base_url_decoded = urllib.parse.unquote(base_url)
        except Exception:
            base_url_decoded = base_url
            
        # --- 保持原有的目标 URL 构建逻辑 ---
        other_params = {}
        for key, value in params.items():
            if key and key not in ['ip', 'u', 'url']:
                other_params[key] = value
                
        target_url = base_url_decoded
        if other_params:
            query_parts = []
            for key, value in other_params.items():
                encoded_value = urllib.parse.quote_plus(value, safe=':/,')
                query_parts.append(f"{key}={encoded_value}")
            query_string = '&'.join(query_parts)
            connector = '&' if '?' in target_url else '?'
            target_url += connector + query_string

        # --- 保持原有的最终代理 URL 编码逻辑 ---
        encoded_params = []
        encoded_params.append(f"ip={urllib.parse.quote(ip, safe='')}")
        encoded_params.append(f"u={urllib.parse.quote(base_url, safe='')}")
        
        for key, value in other_params.items():
            encoded_value = urllib.parse.quote_plus(value, safe='')
            encoded_params.append(f"{key}={encoded_value}")
        
        proxy_url = f"{self.address}?{'&'.join(encoded_params)}"

        return {
            "url": proxy_url,
            "socks5": ip,
            "m3u8_url": target_url
        }

    def proxy(self, url: str, headers: Dict[str, Any]) -> Tuple[Union[bytes, Iterable[bytes]], Dict[str, str]]:
        socket.getaddrinfo = getaddrinfo_ipv4_only
        try:
            parsed_url = urllib.parse.urlparse(url)
            qs = urllib.parse.parse_qs(parsed_url.query, keep_blank_values=True)
            
            ip = qs.get('ip', [''])[0]
            base_url = qs.get('u', [''])[0]
            if not ip or not base_url:
                return self._err("缺少必要参数", 400)
            
            # --- 保持原有的目标 URL 重构逻辑 ---
            target = urllib.parse.unquote(base_url)
            other_params = {}
            for key, values in qs.items():
                if key and key not in ['ip', 'u', 'url']:
                    other_params[key] = urllib.parse.unquote(values[0])
            
            if other_params:
                query_parts = [f"{k}={urllib.parse.quote_plus(v, safe=':/,')}" for k, v in other_params.items()]
                target += ('&' if '?' in target else '?') + '&'.join(query_parts)
            
            proxy = self._get_proxy(ip)
            is_m3u8 = '.m3u8' in target.lower()
            
            req_headers = {k: v for k, v in headers.items() if k.lower() in ['range', 'user-agent']}
            r = self.session.get(
                target,
                proxies=proxy,
                headers=req_headers,
                timeout=(3 if is_m3u8 else 8),
                verify=False,
                stream=not is_m3u8
            )
            
            if r.status_code >= 400:
                return self._err(f"目标请求失败: {r.status_code}", r.status_code)

            if is_m3u8:
                all_params = {k: v[0] for k, v in qs.items() if k != 'url'}
                b = self._rewrite_m3u8(r.text, target, ip, all_params).encode('utf-8')
                h = {'Content-Type': 'application/vnd.apple.mpegurl', 'Content-Length': str(len(b))}
                return b, self._add_common_headers(h, r.status_code)
            else:
                h = {
                    'Content-Type': r.headers.get('Content-Type', 'video/mp2t'),
                    **{k: v for k, v in r.headers.items() if k.lower() in ['content-length', 'content-range', 'transfer-encoding']}
                }
                return r.iter_content(chunk_size=8192), self._add_common_headers(h, r.status_code)

        except Exception as e:
            return self._err(str(e), 500)
        finally:
            socket.getaddrinfo = original_getaddrinfo

    def _rewrite_m3u8(self, content: str, base_url: str, ip: str, original_params: Dict[str, str]) -> str:
        """重写逻辑完全保留，确保分段 URL 处理与原版一致"""
        if not content.strip(): return content
        url_parts = urllib.parse.urlparse(base_url)
        base_dir = base_url.rsplit('/', 1)[0] + '/'
        base_root = f"{url_parts.scheme}://{url_parts.netloc}"
        lines = []
        
        for l in content.splitlines():
            l = l.strip()
            if not l: continue
            
            if l.startswith("#"):
                if l.upper().startswith('#EXT-X-KEY'):
                    parts = l.split(',')
                    new_parts = []
                    for part in parts:
                        if part.upper().startswith('URI='):
                            uri_val = part[4:].strip().strip('"')
                            abs_url = urllib.parse.urljoin(base_dir, uri_val) if not uri_val.startswith("http") else uri_val
                            if uri_val.startswith("/"): abs_url = f"{base_root}{uri_val}"
                            
                            # 严格遵循原有的参数拼接和编码
                            p_parts = [f"ip={urllib.parse.quote(ip)}", f"u={urllib.parse.quote_plus(abs_url, safe='')}"]
                            for k, v in original_params.items():
                                if k not in ['ip', 'u']:
                                    p_parts.append(f"{k}={urllib.parse.quote_plus(v, safe='')}")
                            
                            new_parts.append(f'URI="{self.address}?{"&".join(p_parts)}"')
                        else:
                            new_parts.append(part)
                    lines.append(','.join(new_parts))
                else:
                    lines.append(l)
                continue
            
            # 处理分段 URL
            full = urllib.parse.urljoin(base_dir, l) if not l.startswith("http") else l
            if l.startswith("/"): full = f"{base_root}{l}"
            
            p_parts = [f"ip={urllib.parse.quote(ip)}", f"u={urllib.parse.quote_plus(full, safe='')}"]
            for k, v in original_params.items():
                if k not in ['ip', 'u']:
                    p_parts.append(f"{k}={urllib.parse.quote_plus(v, safe='')}")
            
            lines.append(f"{self.address}?{'&'.join(p_parts)}")
            
        return "\n".join(lines)

    def _add_common_headers(self, headers: Dict[str, str], status_code: int) -> Dict[str, str]:
        headers.update({"Access-Control-Allow-Origin": "*", "X-Proxy-Status-Code": str(status_code)})
        return headers

    def _err(self, msg: str, status_code: int = 500) -> Tuple[bytes, Dict[str, str]]:
        b = f"[Error {status_code}] {msg}".encode('utf-8')
        return b, self._add_common_headers({"Content-Type": "text/plain", "Content-Length": str(len(b))}, status_code)

    def stop(self):
        if hasattr(self, 'session'): self.session.close()

    def __del__(self):
        self.stop()
