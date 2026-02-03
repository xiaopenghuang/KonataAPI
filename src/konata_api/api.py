import requests


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
        if token_data.get("code") and "data" in token_data:
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
        headers = {}
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
        resp.raise_for_status()

        # 检查响应内容是否为空
        if not resp.text.strip():
            return {"error": "API 返回空响应，请检查接口路径是否正确"}

        try:
            data = resp.json()
        except ValueError:
            # JSON 解析失败，返回原始内容的前200字符
            preview = resp.text[:200] if len(resp.text) > 200 else resp.text
            return {"error": f"API 返回非 JSON 格式: {preview}"}

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
        return {"error": str(e)}


if __name__ == "__main__":
    # 测试用法示例
    # test_key = "sk-your-api-key"
    # base_url = "https://your-api-url.com"
    # result = query_balance(test_key, base_url)
    # print("余额:", result)
    pass
