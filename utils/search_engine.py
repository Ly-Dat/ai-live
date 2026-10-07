import requests
from bs4 import BeautifulSoup
from loguru import logger
from typing import List, Dict, Optional
from functools import lru_cache

class SearchEngine:
    """
    Search engine class, used to perform web searches and get result summaries.
    Supports the Google, Bing and Baidu search engines.
    """

    def __init__(self, headers: Dict[str, str], proxies: Optional[Dict[str, str]] = None):
        """
        Initialize the search engine instance.

        :param headers: Request headers, used to simulate browser behavior
        :param proxies: Proxy settings (optional)
        """
        self.headers = headers
        self.proxies = proxies

    @lru_cache(maxsize=100)
    def search(self, query: str, engine: str = 'google', engine_id: int = 1) -> List[Dict[str, str]]:
        """
        Perform a search and return the results.

        :param query: Search query
        :param engine: Search engine name (google, bing or baidu)
        :param engine_id: Search engine ID (Google only)
        :return: Search result list, each result contains a title and a link
        """
        search_functions = {
            'google': self._google_search,
            'bing': self._bing_search,
            'baidu': self._baidu_search
        }
        
        search_function = search_functions.get(engine.lower())
        if not search_function:
            raise ValueError(f"Unsupported search engine:{engine}")
        
        return search_function(query, engine_id)

    def _google_search(self, query: str, engine_id: int) -> List[Dict[str, str]]:
        """Perform a Google search"""
        if engine_id == 1:
            url = f"https://www.google.com/search?q={query}"
            soup = self._get_soup(url)
            return self._parse_google_results(soup)
        elif engine_id == 2:
            url = "https://lite.duckduckgo.com/lite/"
            data = {"q": query}
            soup = self._get_soup(url, method='post', data=data)
            return self._parse_duckduckgo_results(soup)
        else:
            raise ValueError(f"Unsupported Google search engine ID:{engine_id}")

    def _bing_search(self, query: str, _: int) -> List[Dict[str, str]]:
        """Perform a Bing search"""
        url = f"https://www.bing.com/search?q={query}"
        soup = self._get_soup(url)
        return self._parse_bing_results(soup)

    def _baidu_search(self, query: str, _: int) -> List[Dict[str, str]]:
        """Perform a Baidu search"""
        url = f"https://www.baidu.com/s?wd={query}"
        soup = self._get_soup(url)
        return self._parse_baidu_results(soup)

    def _get_soup(self, url: str, method: str = 'get', **kwargs) -> BeautifulSoup:
        """
        Get the web page content and parse it into a BeautifulSoup object.

        :param url: TargetURL
        :param method: HTTPMethod (get or post)
        :param kwargs: Other request parameters
        :return: BeautifulSoupObject
        """
        try:
            if method == 'get':
                response = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=30, **kwargs)
            elif method == 'post':
                response = requests.post(url, headers=self.headers, proxies=self.proxies, timeout=30, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method:{method}")
            
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Error occurred while fetching URL {url}:{str(e)}")
            raise

    def _parse_google_results(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Parse Google search results"""
        results = []
        for g in soup.find_all('div', class_='g'):
            anchors = g.find_all('a')
            if anchors:
                link = anchors[0]['href']
                if link.startswith('/url?q='):
                    link = link[7:]
                if not link.startswith('http'):
                    continue
                title = g.find('h3').text
                results.append({'title': title, 'link': link})
        return results

    def _parse_duckduckgo_results(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Parse DuckDuckGo search results"""
        results = []
        for g in soup.find_all("a"):
            results.append({'title': g.text, 'link': g['href']})
        return results

    def _parse_bing_results(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Parse Bing search results"""
        results = []
        for b in soup.find_all('li', class_='b_algo'):
            anchors = b.find_all('a')
            if anchors:
                link = next((a['href'] for a in anchors if 'href' in a.attrs), None)
                if link:
                    title = b.find('h2').text
                    results.append({'title': title, 'link': link})
        return results

    def _parse_baidu_results(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Parse Baidu search results"""
        results = []
        for b in soup.find_all('div', class_='result'):
            anchors = b.find_all('a')
            if anchors:
                link = anchors[0]['href']
                title = b.find('h3').text
                if link.startswith('/link?url='):
                    link = "https://www.baidu.com" + link
                results.append({'title': title, 'link': link})
        return results

    def get_content(self, url: str) -> Optional[str]:
        """
        Get the web page content.

        :param url: TargetURL
        :return: Web page content text, returned if an error occursNone
        """
        try:
            soup = self._get_soup(url)
            paragraphs = soup.find_all(['p', 'span'])
            content = ' '.join([p.get_text() for p in paragraphs])
            return self._trim_content(content)
        except Exception as e:
            logger.error(f"Error occurred while fetching content from {url}:{str(e)}")
            return None

    @staticmethod
    def _trim_content(content: str, max_length: int = 8000) -> str:
        """
        Trim the content to the specified maximum length.

        :param content: Original content
        :param max_length: Maximum length
        :return: Trimmed content
        """
        if len(content) <= max_length:
            return content
        start = (len(content) - max_length) // 2
        return content[start:start + max_length]

    def get_summaries(self, query: str, engine: str = 'google', engine_id: int = 1, count: int = 3) -> List[str]:
        """
        Get the summaries of the search results.

        :param query: Search query
        :param engine: Search engine name
        :param engine_id: Search engineID
        :param count: Number of summaries to fetch
        :return: Summary list
        """
        search_results = self.search(query, engine, engine_id)
        summaries = []
        for result in search_results[:count]:
            content = self.get_content(result['link'])
            if content and len(content) >= 50:
                summaries.append(content)
        return summaries

def search_online(query: str, engine: str = 'google', engine_id: int = 1, count: int = 3, 
                  headers: Optional[Dict[str, str]] = None, 
                  proxies: Optional[Dict[str, str]] = None) -> List[str]:
    """
    Search online and get summaries.

    :param query: Search query
    :param engine: Search engine name
    :param engine_id: Search engineID
    :param count: Number of summaries to fetch
    :param headers: Request headers (optional)
    :param proxies: Proxy settings (optional)
    :return: Summary list
    """
    # If no headers are provided, use the defaults
    if headers is None:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
            'Content-Type': 'text/plain',
        }

    logger.info(f"Start searching: {query} (using {engine} engine)")
    search_engine = SearchEngine(headers, proxies)
    return search_engine.get_summaries(query, engine, engine_id, count)

def main():
    """Main function, demonstrates the use of the search engine"""
    proxies = None  # If a proxy is needed, uncomment and fill in the correct proxy information
    # proxies = {
    #     "http": "http://127.0.0.1:10809",
    #     "https": "http://127.0.0.1:10809",
    #     "socks5": "socks://127.0.0.1:10808"
    # }

    query = "伊卡洛斯"
    engine = "baidu"
    engine_id = 1
    count = 3

    summaries = search_online(query, engine, engine_id, count, proxies=proxies)
    for i, summary in enumerate(summaries, 1):
        logger.info(f"Summary {i}:\n{summary}\n")

if __name__ == '__main__':
    logger.add("Log.txt", rotation="500 MB", retention="30 days", compression="zip", encoding="utf-8")
    logger.info("Search engine program started")
    main()
    logger.info("Search engine program ended")