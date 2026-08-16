"""Safely overlay the non-secret Monitor settings stored in Cloudflare KV."""

import copy
import json
import urllib.error
import urllib.request


def settings_payload(config: dict) -> dict:
    """Build the browser/Worker config shape from repository-owned defaults."""
    return {
        "topics": {
            theme["topic_id"]: {
                "display_name": theme.get("display_name", theme["name"]),
                "criteria": theme.get("filter_prompt", ""),
                "threshold": int(theme.get("threshold", 6)),
                "sources": {
                    source["source_id"]: {
                        "name": source["name"], "url": source["url"],
                        "enabled": bool(source.get("enabled", True)), "user_added": bool(source.get("user_added", False)),
                    }
                    for source in theme.get("sources", [])
                },
            }
            for theme in config.get("themes", [])
        },
        "run": {
            "times": list(config.get("run", {}).get("times", [])),
            "keep_below_threshold": bool(config.get("run", {}).get("keep_below_threshold", True)),
            "read_dim_enabled": bool(config.get("run", {}).get("read_dim_enabled", True)),
        },
    }


def _valid_time(value: object) -> bool:
    return isinstance(value, str) and len(value) == 5 and value[2] == ":" and value[:2].isdigit() and value[3:].isdigit() and 0 <= int(value[:2]) <= 23 and 0 <= int(value[3:]) <= 59


def apply_settings(default_config: dict, settings: object) -> dict:
    """Apply only known, validated runtime values; malformed KV data changes nothing."""
    config = copy.deepcopy(default_config)
    if not isinstance(settings, dict):
        return config
    topics = settings.get("topics")
    if isinstance(topics, dict):
        for theme in config.get("themes", []):
            saved = topics.get(theme["topic_id"])
            if not isinstance(saved, dict):
                continue
            name, criteria, threshold, sources = saved.get("display_name"), saved.get("criteria"), saved.get("threshold"), saved.get("sources")
            if isinstance(name, str) and 0 < len(name.strip()) <= 80:
                theme["display_name"] = name.strip()
            if isinstance(criteria, str) and 0 < len(criteria.strip()) <= 4_000:
                theme["filter_prompt"] = criteria.strip()
            if isinstance(threshold, int) and not isinstance(threshold, bool) and 1 <= threshold <= 10:
                theme["threshold"] = threshold
            if isinstance(sources, dict):
                standard_ids = {source.get("source_id") for source in theme.get("sources", [])}
                for source in theme.get("sources", []):
                    saved_source = sources.get(source.get("source_id"))
                    enabled = saved_source.get("enabled") if isinstance(saved_source, dict) else saved_source
                    if isinstance(enabled, bool): source["enabled"] = enabled
                for source_id, saved_source in sources.items():
                    if source_id in standard_ids or not isinstance(saved_source, dict): continue
                    if (saved_source.get("user_added") is True and isinstance(saved_source.get("name"), str)
                            and isinstance(saved_source.get("url"), str) and isinstance(saved_source.get("enabled"), bool)):
                        theme.setdefault("sources", []).append({"source_id": source_id, "name": saved_source["name"], "url": saved_source["url"], "enabled": saved_source["enabled"], "user_added": True})
    run = settings.get("run")
    if isinstance(run, dict):
        times = run.get("times")
        if isinstance(times, list) and 1 <= len(times) <= 12 and all(_valid_time(value) for value in times):
            config.setdefault("run", {})["times"] = sorted(set(times))
        for key in ("keep_below_threshold", "read_dim_enabled"):
            if isinstance(run.get(key), bool):
                config.setdefault("run", {})[key] = run[key]
    return config


def fetch_settings(url: str, timeout: float = 5.0) -> dict | None:
    """Read Worker config without a browser Origin. Fail closed to YAML defaults."""
    if not url:
        return None
    try:
        request = urllib.request.Request(url.rstrip("/") + "/config", headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("config") if isinstance(payload, dict) else None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as error:
        print(f"警告: 設定APIを取得できません。リポジトリ既定値を使用します: {error}")
        return None
