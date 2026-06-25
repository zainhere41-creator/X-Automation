import xml.etree.ElementTree as ET
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_xml(file_path: str) -> list[dict]:
    """
    Parse and validate XML post data file.
    Returns list of valid post dictionaries with title, url, and optional community_url keys.
    
    XML Format:
    <posts>
        <post>
            <title>Tweet text here</title>
            <url>https://example.com/article</url>
            <community_url>https://twitter.com/i/communities/123456789</community_url>
        </post>
    </posts>
    """
    file_path = Path(file_path)
    
    if not file_path.is_file():
        logger.error(f"XML file not found: {file_path}")
        return []
    
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except ET.ParseError as e:
        logger.error(f"XML parse error in {file_path}: {e}")
        return []
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        return []
    
    posts = []
    for i, post_el in enumerate(root.iter("post"), start=1):
        title_el = post_el.find("title")
        url_el = post_el.find("url")
        community_url_el = post_el.find("community_url")
        
        # Validate title
        if title_el is None or not title_el.text or not title_el.text.strip():
            logger.warning(f"Post {i}: Missing or empty title, skipping")
            continue
        
        # Validate URL
        if url_el is None or not url_el.text:
            logger.warning(f"Post {i}: Missing URL, skipping")
            continue
        
        url = url_el.text.strip()
        if not url.startswith(("http://", "https://")):
            logger.warning(f"Post {i}: Invalid URL '{url}', skipping")
            continue
        
        # Parse optional community URL
        community_url = None
        if community_url_el is not None and community_url_el.text:
            community_url = community_url_el.text.strip()
            if not community_url.startswith(("http://", "https://")):
                logger.warning(f"Post {i}: Invalid community URL '{community_url}', ignoring")
                community_url = None
            else:
                logger.info(f"Post {i}: Community URL found: {community_url}")
        
        # Valid post
        post_data = {
            "title": title_el.text.strip(),
            "url": url
        }
        
        if community_url:
            post_data["community_url"] = community_url
        
        posts.append(post_data)
    
    logger.info(f"Loaded {len(posts)} valid posts from {file_path}")
    return posts
