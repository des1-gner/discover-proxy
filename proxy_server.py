from flask import Flask, request, Response, redirect
import requests
from urllib.parse import urlparse, urljoin
import re

app = Flask(__name__)

# Optional: Use a residential proxy for the outbound requests
# Leave empty to use your local IP
OUTBOUND_PROXY = {
    # 'http': 'http://139.162.78.109:8080',
    # 'https': 'http://139.162.78.109:8080'
}

# Track which domain we're proxying
CURRENT_TARGET = None

def rewrite_urls(content, original_host, proxy_host):
    """Rewrite URLs in HTML/CSS/JS to go through our proxy"""
    content = content.replace(f'https://{original_host}', f'http://{proxy_host}/{original_host}')
    content = content.replace(f'http://{original_host}', f'http://{proxy_host}/{original_host}')
    content = content.replace(f'//{original_host}', f'//{proxy_host}/{original_host}')
    return content

@app.route('/<path:full_path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def proxy(full_path):
    """
    Proxy requests to the target website
    URL format: http://your-proxy.ngrok.io/www.example.com/path
    """
    
    # Extract the target domain and path
    parts = full_path.split('/', 1)
    target_domain = parts[0]
    target_path = parts[1] if len(parts) > 1 else ''
    
    # Build the full target URL
    target_url = f"https://{target_domain}/{target_path}"
    
    print(f"\n📨 Proxying: {request.method} {target_url}")
    
    # Copy headers from the original request
    headers = {key: value for key, value in request.headers if key.lower() not in ['host', 'connection']}
    headers['Host'] = target_domain
    
    # Make the request to the target
    try:
        if OUTBOUND_PROXY:
            response = requests.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False,
                proxies=OUTBOUND_PROXY,
                timeout=30
            )
        else:
            response = requests.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False,
                timeout=30
            )
        
        # Handle redirects
        if 300 <= response.status_code < 400 and 'Location' in response.headers:
            location = response.headers['Location']
            # Rewrite redirect location to go through our proxy
            if location.startswith('http'):
                parsed = urlparse(location)
                new_location = f"/{parsed.netloc}{parsed.path}"
                if parsed.query:
                    new_location += f"?{parsed.query}"
                print(f"🔄 Rewriting redirect: {location} -> {new_location}")
                return redirect(new_location, code=response.status_code)
        
        # Prepare response headers
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = {k: v for k, v in response.headers.items() if k.lower() not in excluded_headers}
        
        # Rewrite content for HTML/CSS/JS
        content = response.content
        content_type = response.headers.get('Content-Type', '')
        
        if 'text/html' in content_type or 'text/css' in content_type or 'javascript' in content_type:
            try:
                text_content = content.decode('utf-8')
                proxy_host = request.host
                text_content = rewrite_urls(text_content, target_domain, proxy_host)
                content = text_content.encode('utf-8')
            except:
                pass  # If decoding fails, return as-is
        
        print(f"✅ Response: {response.status_code}")
        
        return Response(
            content,
            status=response.status_code,
            headers=response_headers
        )
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return Response(f"Proxy Error: {str(e)}", status=500)

@app.route('/')
def index():
    return """
    <h1>Proxy Server Running</h1>
    <p>Usage: http://your-proxy-url/target-domain.com/path</p>
    <p>Example: http://localhost:5000/www.discovercard.com/application/preapproval/initial</p>
    """

if __name__ == '__main__':
    print("🚀 Starting proxy server...")
    print("📝 Access format: http://localhost:5000/target-domain.com/path")
    app.run(host='0.0.0.0', port=5000, debug=True)
