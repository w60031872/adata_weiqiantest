# -*- coding: utf-8 -*-
"""
代理:https://jahttp.zhimaruanjian.com/getapi/

@desc: adata 请求工具类
@author: 1nchaos
@time:2023/3/30
@log: 封装请求次数
"""

import threading
import time
from collections import defaultdict
from urllib.parse import urlparse

import requests


class SunProxy(object):
    _data = {}
    _instance_lock = threading.Lock()

    def __init__(self):
        pass

    def __new__(cls, *args, **kwargs):
        if not hasattr(SunProxy, "_instance"):
            with SunProxy._instance_lock:
                if not hasattr(SunProxy, "_instance"):
                    SunProxy._instance = object.__new__(cls)

    @classmethod
    def set(cls, key, value):
        cls._data[key] = value

    @classmethod
    def get(cls, key):
        return cls._data.get(key)

    @classmethod
    def delete(cls, key):
        if key in cls._data:
            del cls._data[key]


class DomainRateLimiter:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._requests = defaultdict(list)
        self._limits = defaultdict(lambda: {'max_requests': 30, 'window': 60})
        self._limiter_lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def set_limit(self, domain: str, max_requests: int = 30, window: int = 60):
        with self._limiter_lock:
            self._limits[domain]['max_requests'] = max_requests
            self._limits[domain]['window'] = window

    def get_limit(self, domain: str) -> dict:
        return dict(self._limits.get(domain, {'max_requests': 30, 'window': 60}))

    def _get_domain(self, url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc or ''

    def acquire(self, url: str) -> bool:
        if not url:
            return True
        domain = self._get_domain(url)
        if not domain:
            return True

        with self._limiter_lock:
            limit = self._limits.get(domain, {'max_requests': 30, 'window': 60})
            max_requests = limit['max_requests']
            window = limit['window']

            now = time.time()
            self._requests[domain] = [t for t in self._requests[domain] if now - t < window]

            if len(self._requests[domain]) >= max_requests:
                sleep_time = self._requests[domain][0] + window - now
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    now = time.time()
                    self._requests[domain] = [t for t in self._requests[domain] if now - t < window]

            self._requests[domain].append(now)
            return True


rate_limiter = DomainRateLimiter.get_instance()


class SunRequests(object):
    def __init__(self, sun_proxy: SunProxy = None) -> None:
        super().__init__()
        self.sun_proxy = sun_proxy

    def request(self, method='get', url=None, times=3, retry_wait_time=1588, proxies=None, wait_time=None, **kwargs):
        """
        简单封装的请求，参考requests，增加循环次数和次数之间的等待时间
        :param proxies: 代理配置
        :param method: 请求方法： get；post
        :param url: url
        :param times: 次数，int
        :param retry_wait_time: 重试等待时间，毫秒
        :param wait_time: 等待时间：毫秒；表示每个请求的间隔时间，在请求之前等待sleep，主要用于防止请求太频繁的限制。
        :param kwargs: 其它 requests 参数，用法相同
        :return: res
        """
        rate_limiter.acquire(url)
        proxies = self.__get_proxies(proxies)
        # 2. 请求数据结果
        res = None
        for i in range(times):
            if wait_time:
                time.sleep(wait_time / 1000)
            res = requests.request(method=method, url=url, proxies=proxies, **kwargs)
            if res.status_code in (200, 404):
                return res
            time.sleep(retry_wait_time / 1000)
            if i == times - 1:
                return res
        return res

    def __get_proxies(self, proxies):
        """
        获取代理配置
        """
        if proxies is None:
            proxies = {}
        is_proxy = SunProxy.get('is_proxy')
        ip = SunProxy.get('ip')
        proxy_url = SunProxy.get('proxy_url')
        if not ip and is_proxy and proxy_url:
            ip = requests.get(url=proxy_url).text.replace('\r\n', '') \
                .replace('\r', '').replace('\n', '').replace('\t', '')
        if is_proxy and ip:
            proxies = {'https': f"http://{ip}", 'http': f"http://{ip}"}
        return proxies


sun_requests = SunRequests()
