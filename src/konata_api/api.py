from typing import Optional
import os
from datetime import datetime
import requests
from konata_api.utils import get_exe_dir, load_config


def _should_log_debug() -> bool:
    config = load_config()
    return bool(config.get("debug", {}).get("enable_api_log", False))


def _log_debug(message: str):
    if not _should_log_debug():
        return
    try:
        log_dir = os.path.join(get_exe_dir(), "debug")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "requests.log")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def _describe_http_response(status_code: int, text: str, content_type: str = "") -> str:
    content = (text or "").strip()
    lower = content.lower()
    ct = (content_type or "").lower()

    is_cf = (
        "cloudflare" in lower
        or "cf-ray" in lower
        or "cf-error" in lower
        or "error code 502" in lower
        or "error code 503" in lower
        or "error code 504" in lower
    )
    if status_code >= 500 and (is_cf or "text/html" in ct or lower.startswith("<!doctype html")):
        return "Cloudflare/源站 5xx 错误：上游异常或暂时不可用"

    if "text/html" in ct or lower.startswith("<!doctype html"):
        return "返回 HTML 页面，可能被 WAF 拦截或登录态失效"

    if content:
        preview = content[:200] + ("..." if len(content) > 200 else "")
        return preview
    return "空响应或未知错误"


DEFAULT_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0"
)


def _build_cookie_headers(base_url: str, session_cookie: str, user_id: str = "", include_content_type: bool = False) -> dict:
    base = base_url.rstrip("/")
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "User-Agent": DEFAULT_BROWSER_USER_AGENT,
        "Referer": f"{base}/console",
        "Origin": base,
        "Cookie": session_cookie,
    }
    if include_content_type:
        headers["Content-Type"] = "application/json"
    if user_id:
        headers["new-api-user"] = user_id
    return headers


def query_balance(
    api_key: str,
    base_url: str = "",
    subscription_api: str = "/v1/dashboard/billing/subscription",
    usage_api: str = "/v1/dashboard/billing/usage",
    auth_type: str = "bearer"
) -> dict:
    """
    查询中转站余额（USD 和 Token 两种统计）
    支持自动检测多种 API 体系

    Args:
        api_key: API Key (sk-xxx 格式) 或 JWT Token
        base_url: API 基础地址
        subscription_api: 订阅信息接口路径
        usage_api: 用量信息接口路径
        auth_type: 认证方式，"bearer" 使用 Header 认证，"url_key" 使用 URL 参数

    Returns:
        dict: 包含余额信息的字典
    """
    base = base_url.rstrip("/")

    # 根据认证类型构建请求参数
    if auth_type == "url_key":
        headers = {"Content-Type": "application/json"}
        auth_params = {"key": api_key}
    else:  # bearer (默认)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        auth_params = {}

    result = {}
    raw_responses = {}  # 保存原始返回数据
    openai_api_success = False

    # 1. 尝试 OpenAI 兼容 API
    try:
        params = {**auth_params}
        sub_resp = requests.get(
            f"{base}{subscription_api}", headers=headers, params=params if params else None, timeout=10
        )
        sub_resp.raise_for_status()
        sub_data = sub_resp.json()
        raw_responses["subscription"] = sub_data

        # 检查是否是新 API 体系 (code/message/data 格式)
        if sub_data.get("code") == 0 and "data" in sub_data:
            data = sub_data["data"]
            # /api/v1/auth/me 格式
            if "balance" in data:
                result["balance"] = data.get("balance", 0)
                result["email"] = data.get("email", "")
                result["status"] = data.get("status", "")
                openai_api_success = True
        elif "hard_limit_usd" in sub_data:
            # OpenAI 兼容格式
            openai_api_success = True
            result["hard_limit_usd"] = sub_data.get("hard_limit_usd", 0)

            # 计算日期范围（最近 100 天）
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=100)

            usage_params = {
                **auth_params,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
            }
            usage_resp = requests.get(
                f"{base}{usage_api}",
                headers=headers,
                params=usage_params,
                timeout=10,
            )
            usage_resp.raise_for_status()
            usage_data = usage_resp.json()
            raw_responses["usage"] = usage_data
            total_usage_cents = usage_data.get("total_usage", 0)
            result["used_usd"] = round(total_usage_cents / 100, 2)
            result["remaining_usd"] = round(
                result["hard_limit_usd"] - result["used_usd"], 2
            )
    except requests.exceptions.RequestException:
        pass  # billing API 可能不可用，继续尝试其他接口

    # 2. 如果 OpenAI API 失败，尝试 sub2api 格式 (/v1/usage)
    if not openai_api_success:
        try:
            usage_resp = requests.get(
                f"{base}/v1/usage", headers=headers, params=auth_params if auth_params else None, timeout=10
            )
            # 不管状态码，先尝试解析 JSON（sub2api 可能返回 403 + JSON 错误信息）
            try:
                usage_data = usage_resp.json()
                raw_responses["v1_usage"] = usage_data

                # 检查是否返回错误码（如 INSUFFICIENT_BALANCE）
                if "code" in usage_data and "message" in usage_data:
                    # 站点返回了错误信息
                    error_code = usage_data.get("code", "")
                    error_msg = usage_data.get("message", "")
                    if error_code == "INSUFFICIENT_BALANCE":
                        result["error"] = f"余额不足: {error_msg}"
                    elif error_code == "INVALID_API_KEY":
                        result["error"] = f"API Key 无效: {error_msg}"
                    else:
                        result["error"] = f"{error_code}: {error_msg}"
                    openai_api_success = True  # 标记已处理，不再尝试其他接口

                # sub2api /v1/usage 格式
                elif "balance" in usage_data or "remaining" in usage_data:
                    openai_api_success = True
                    result["balance"] = usage_data.get("balance", usage_data.get("remaining", 0))
                    result["remaining"] = usage_data.get("remaining", 0)
                    result["plan_name"] = usage_data.get("planName", "")
                    result["unit"] = usage_data.get("unit", "USD")

                    # 解析 usage 统计
                    usage = usage_data.get("usage", {})
                    if usage:
                        today = usage.get("today", {})
                        total = usage.get("total", {})
                        result["today_requests"] = today.get("requests", 0)
                        result["today_tokens"] = today.get("total_tokens", 0)
                        result["today_cost"] = today.get("cost", 0)
                        result["total_requests"] = total.get("requests", 0)
                        result["total_tokens"] = total.get("total_tokens", 0)
                        result["total_cost"] = total.get("cost", 0)
            except ValueError:
                # JSON 解析失败，检查 HTTP 状态码
                if usage_resp.status_code != 200:
                    pass  # 继续尝试其他接口
        except requests.exceptions.RequestException:
            pass

    # 3. 如果还是失败，尝试 /api/v1/auth/me (JWT Token 认证的站点)
    if not openai_api_success:
        try:
            me_resp = requests.get(
                f"{base}/api/v1/auth/me", headers=headers, params=auth_params if auth_params else None, timeout=10
            )
            me_resp.raise_for_status()
            me_data = me_resp.json()
            raw_responses["auth_me"] = me_data

            if me_data.get("code") == 0 and "data" in me_data:
                data = me_data["data"]
                result["balance"] = data.get("balance", 0)
                result["email"] = data.get("email", "")
                result["status"] = data.get("status", "")
        except requests.exceptions.RequestException:
            pass

    # 4. 尝试新 API 体系用量统计 (/api/v1/usage/dashboard/stats)
    # 如果配置了新 API 路径，或者 OpenAI API 失败时自动尝试
    should_try_new_stats = "/api/v1/" in usage_api or not openai_api_success
    if should_try_new_stats and "today_requests" not in result:
        stats_url = usage_api if "/api/v1/" in usage_api else "/api/v1/usage/dashboard/stats"
        try:
            stats_resp = requests.get(
                f"{base}{stats_url}", headers=headers, params=auth_params if auth_params else None, timeout=10
            )
            stats_resp.raise_for_status()
            stats_data = stats_resp.json()
            raw_responses["stats"] = stats_data

            if stats_data.get("code") == 0 and "data" in stats_data:
                data = stats_data["data"]
                result["total_requests"] = data.get("total_requests", 0)
                result["total_tokens"] = data.get("total_tokens", 0)
                result["total_cost"] = data.get("total_cost", 0)
                result["today_requests"] = data.get("today_requests", 0)
                result["today_tokens"] = data.get("today_tokens", 0)
                result["today_cost"] = data.get("today_cost", 0)
        except requests.exceptions.RequestException:
            pass

    # 4. 查询 Token 用量 (NewAPI 风格)
    try:
        token_params = {**auth_params} if auth_params else None
        token_resp = requests.get(
            f"{base}/api/usage/token/", headers=headers, params=token_params, timeout=10
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        raw_responses["token"] = token_data
        if token_data.get("code") == 0 and "data" in token_data:
            data = token_data["data"]
            result["total_granted"] = data.get("total_granted", 0)
            result["total_used"] = data.get("total_used", 0)
            result["total_available"] = data.get("total_available", 0)
    except requests.exceptions.RequestException:
        pass  # token API 可能不可用

    if not result:
        result["error"] = "无法获取余额信息"

    result["raw_response"] = raw_responses
    return result


def query_logs(
    api_key: str,
    base_url: str,
    page_size: int = 50,
    page: int = 1,
    order: str = "desc",
    custom_api_path: str = "",
    proxy_url: str = "",
    auth_type: str = "bearer",
) -> dict:
    """
    查询调用日志（使用 API Key）

    Args:
        api_key: API Key (sk-xxx 格式) 或 JWT Token
        base_url: API 基础地址
        page_size: 每页返回多少条日志（默认 50）
        page: 页码（默认 1）
        order: 排序方式，desc=降序/最新在前，asc=升序（默认 desc）
        custom_api_path: 自定义日志接口路径（如 /api/log/custom），留空使用默认 /api/log/token
        proxy_url: 代理地址（如 https://proxy.cifang.xyz/proxy），留空则直接访问
        auth_type: 认证方式，"bearer" 使用 Header 认证，"url_key" 使用 URL 参数

    Returns:
        dict: 包含日志列表的字典
            - total: 总条数
            - items: 日志列表，每条包含 model_name, token_name, quota,
                     prompt_tokens, completion_tokens, created_at 等
            - raw_response: 原始 API 返回数据
    """
    from urllib.parse import urlencode, quote

    base = base_url.rstrip("/")
    api_path = custom_api_path.strip() if custom_api_path else "/api/log/token"

    # 根据认证类型构建请求
    if auth_type == "url_key":
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        # 构建目标 URL (URL 参数认证)
        target_url = f"{base}{api_path}?key={api_key}&p={page}&per_page={page_size}&order={order}"

        # 如果有代理，通过代理访问
        if proxy_url.strip():
            request_url = f"{proxy_url.rstrip('/')}?url={quote(target_url, safe='')}"
            params = None
        else:
            request_url = f"{base}{api_path}"
            params = {
                "key": api_key,
                "p": page,
                "per_page": page_size,
                "order": order,
            }
    else:  # bearer (默认)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        # Bearer 认证不在 URL 中传 key
        if proxy_url.strip():
            target_url = f"{base}{api_path}?p={page}&per_page={page_size}&order={order}"
            request_url = f"{proxy_url.rstrip('/')}?url={quote(target_url, safe='')}"
            params = None
        else:
            request_url = f"{base}{api_path}"
            params = {
                "p": page,
                "per_page": page_size,
                "order": order,
            }

    try:
        resp = requests.get(request_url, params=params, headers=headers, timeout=10)
        if resp.status_code != 200:
            detail = _describe_http_response(resp.status_code, resp.text, resp.headers.get("Content-Type", ""))
            _log_debug(f"query_logs {request_url} status={resp.status_code} detail={detail}")
            return {"error": f"HTTP {resp.status_code}: {detail}"}

        # 检查响应内容是否为空
        if not resp.text.strip():
            return {"error": "API 返回空响应，请检查接口路径是否正确"}

        try:
            data = resp.json()
        except ValueError:
            detail = _describe_http_response(resp.status_code, resp.text, resp.headers.get("Content-Type", ""))
            _log_debug(f"query_logs {request_url} json_error detail={detail}")
            return {"error": f"API 返回非 JSON 格式: {detail}"}

        # 保存原始返回数据
        raw_response = data

        # 新接口直接返回 {"data": [...]}
        items = data.get("data", [])

        # 强制按 created_at 降序排序（确保最新的在前面）
        # 因为有些 API 不支持 order 参数
        items = sorted(items, key=lambda x: x.get("created_at", 0), reverse=True)

        return {
            "total": len(items),
            "items": items,
            "raw_response": raw_response
        }
    except requests.exceptions.RequestException as e:
        _log_debug(f"query_logs {request_url} exception={e}")
        return {"error": str(e)}


def do_checkin(
    base_url: str,
    session_cookie: str,
    user_id: str = "",
    checkin_path: str = "/api/user/checkin",
    extra_headers: Optional[dict] = None,
) -> dict:
    """
    执行签到（使用 Session Cookie 认证）

    Args:
        base_url: API 基础地址
        session_cookie: 浏览器 Session Cookie（包含 session=xxx 等）
        user_id: 用户 ID（某些站点需要 new-api-user Header）
        checkin_path: 签到接口路径（默认 /api/user/checkin）
        extra_headers: 额外请求头（JSON 对象）

    Returns:
        dict: 签到结果
            - success: 是否成功
            - message: 提示信息
            - quota_awarded: 获得的额度（成功时）
            - checkin_date: 签到日期（成功时）
    """
    base = base_url.rstrip("/")
    headers = _build_cookie_headers(base, session_cookie, user_id, include_content_type=True)
    if extra_headers:
        headers.update(extra_headers)

    try:
        path = checkin_path.strip() or "/api/user/checkin"
        if not path.startswith("/"):
            path = "/" + path
        resp = requests.post(f"{base}{path}", headers=headers, timeout=15)

        # 检查响应内容类型，判断是否被 Cloudflare 拦截
        content_type = resp.headers.get("Content-Type", "")
        response_text = resp.text

        # 检测 Cloudflare 拦截
        if "text/html" in content_type or response_text.strip().startswith("<!DOCTYPE") or response_text.strip().startswith("<html"):
            detail = _describe_http_response(resp.status_code, response_text, content_type)
            _log_debug(f"checkin {base}{path} status={resp.status_code} detail={detail}")
            return {"success": False, "message": detail}

        # 检查空响应
        if not response_text.strip():
            return {"success": False, "message": "API 返回空响应，请检查 Cookie 是否有效"}

        # 尝试解析 JSON
        try:
            data = resp.json()
        except ValueError:
            detail = _describe_http_response(resp.status_code, response_text, content_type)
            _log_debug(f"checkin {base}{path} json_error detail={detail}")
            return {"success": False, "message": f"API 返回非 JSON: {detail}"}

        message = str(data.get("message") or "").strip()
        if data.get("success"):
            return {
                "success": True,
                "message": message or "签到成功",
                "quota_awarded": data.get("data", {}).get("quota_awarded", 0),
                "checkin_date": data.get("data", {}).get("checkin_date", ""),
            }

        normalized_message = message.lower()
        already_checked_keywords = (
            "已签到",
            "已经签到",
            "今日已签到",
            "already checked",
            "already check",
            "checked in today",
            "already signed",
        )
        if any((keyword in message) or (keyword in normalized_message) for keyword in already_checked_keywords):
            return {
                "success": True,
                "already_checked_in": True,
                "message": message or "今日已签到",
                "quota_awarded": 0,
                "checkin_date": data.get("data", {}).get("checkin_date", ""),
            }

        return {
            "success": False,
            "message": message or "签到失败",
        }
    except requests.exceptions.Timeout:
        _log_debug(f"checkin {base}{path} timeout")
        return {"success": False, "message": "请求超时，请检查网络"}
    except requests.exceptions.ConnectionError:
        _log_debug(f"checkin {base}{path} connection_error")
        return {"success": False, "message": "连接失败，请检查网络或站点是否可访问"}
    except requests.exceptions.RequestException as e:
        _log_debug(f"checkin {base}{path} exception={e}")
        return {"success": False, "message": f"网络错误: {str(e)}"}


def get_checkin_status(base_url: str, session_cookie: str, month: str = None) -> dict:
    """
    获取签到状态（使用 Session Cookie 认证）

    Args:
        base_url: API 基础地址
        session_cookie: 浏览器 Session Cookie
        month: 月份（格式 2026-02），默认当前月

    Returns:
        dict: 签到状态信息
    """
    from datetime import datetime

    base = base_url.rstrip("/")
    if not month:
        month = datetime.now().strftime("%Y-%m")

    headers = _build_cookie_headers(base, session_cookie)

    try:
        resp = requests.get(f"{base}/api/user/checkin", headers=headers, params={"month": month}, timeout=15)
        data = resp.json()

        if data.get("success"):
            return {
                "success": True,
                "data": data.get("data", {}),
            }
        else:
            return {
                "success": False,
                "message": data.get("message", "获取签到状态失败"),
            }
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"网络错误: {str(e)}"}
    except ValueError:
        return {"success": False, "message": "API 返回非 JSON 格式"}


def query_balance_by_cookie(base_url: str, session_cookie: str, user_id: str = "") -> dict:
    """
    使用 Cookie 查询用户余额（通过 /api/user/self 接口）

    Args:
        base_url: API 基础地址
        session_cookie: 浏览器 Session Cookie
        user_id: 用户 ID（某些站点需要 new-api-user Header）

    Returns:
        dict: 用户信息，包含余额
            - success: 是否成功
            - balance: 余额（quota 转换为 USD）
            - username: 用户名
            - email: 邮箱
            - raw_data: 原始返回数据
    """
    base = base_url.rstrip("/")
    headers = _build_cookie_headers(base, session_cookie, user_id)

    try:
        resp = requests.get(f"{base}/api/user/self", headers=headers, timeout=15)
        try:
            data = resp.json()
        except ValueError:
            detail = _describe_http_response(resp.status_code, resp.text, resp.headers.get("Content-Type", ""))
            _log_debug(f"balance_by_cookie {base}/api/user/self json_error detail={detail}")
            return {"success": False, "message": f"API 返回非 JSON 格式: {detail}"}

        if data.get("success") and "data" in data:
            user_data = data["data"]
            # quota 通常是以 500000 为 1 USD 的单位
            quota = user_data.get("quota", 0)
            balance = quota / 500000 if quota else 0

            return {
                "success": True,
                "balance": round(balance, 2),
                "quota": quota,
                "username": user_data.get("username", ""),
                "email": user_data.get("email", ""),
                "display_name": user_data.get("display_name", ""),
                "raw_data": user_data,
            }
        else:
            return {
                "success": False,
                "message": data.get("message", "获取用户信息失败"),
            }
    except requests.exceptions.RequestException as e:
        _log_debug(f"balance_by_cookie {base}/api/user/self exception={e}")
        return {"success": False, "message": f"网络错误: {str(e)}"}


if __name__ == "__main__":
    # 测试用法示例
    # test_key = "sk-your-api-key"
    # base_url = "https://your-api-url.com"
    # result = query_balance(test_key, base_url)
    # print("余额:", result)
    pass
