import urllib.request
from bs4 import BeautifulSoup
u="https://styles.refero.design/"
h=urllib.request.urlopen(u,timeout=30).read().decode()
s=BeautifulSoup(h,"html.parser")
print("STATUS",len(h))
print("STYLES",[(a.get_text(" ",strip=True),a.get("href")) for a in s.select("a[href*=\"/style/\"]")][:65])
print("HEADINGS",[(x.name,x.get_text(" ",strip=True)) for x in s.select("h1,h2,h3")][:30])
print("TEXT",s.get_text(" ",strip=True)[:5000])
