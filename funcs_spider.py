import json
import os
import re
import sys
import logging
from collections import OrderedDict

import scrapy
from scrapy.cmdline import execute
from pyquery import PyQuery as pq

class FunctionParser(object):
    def __init__(self, prefix, syntax):
        self.isFunc = '(' in syntax
        syntax = re.sub(r"(?P<param>\w+)1\s*,?\s*((?P=param)2)?\s*,?\s*((\.+)|(\u2026))\s*,?\s*(?P=param)[nN]", r"\g<param>1_\g<param>N", syntax) # Ellipsis
        if self.isFunc or (syntax.count("=") == 1):
            syntax = re.sub(r".*=\s+(?=[\w.]+\s*(\(|$))", "", syntax) # delete return
        syntax = syntax.replace(",", " ").replace("(", " ").replace(")", "")
        self.identifier = syntax.split()
        self.prefix = prefix

    def getFname(self):
        if len(self.identifier):
            return self.identifier[0]
        return self.prefix

    def genSyntax(self):
        return self._genFunction() if self.isFunc else self._genCommand()

    def _genFunction(self):
        return "{}({})".format(self.getFname(), self.genParams())

    
    def _genCommand(self):
        return "{} {}".format(self.getFname(), self.genParams()).strip()

    def genPlainParams(self):
        sep = r"\, " if self.isFunc else r" "
        return sep.join(self.identifier[1:])

    def genParams(self):
        sep = ", " if self.isFunc else r" "
        return sep.join([param if self._isConst(param) else "${" + param + "}" for param in self.identifier[1:]])

    def _isConst(self, s):
        return  "'" in s or '"' in s or "=" in s or s.startswith("-")


class FunctionsSpider(scrapy.Spider):
    name = "funcs"
    version = "R2020a"
    headers = {
        "User-Agent:": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3879.0 Safari/537.36 Edg/78.0.249.1e"
    }
    baseurl = "https://www.mathworks.com/help/search/reflist/doccenter/en/{}".format(version)
    acceptAllCategorys = True
    acceptCategorys = [
        "matlab", # MATLAB
    ]
    prefix_filter = re.compile('^[0-9a-zA-Z._]+$')

    def start_requests(self):
        urls = [
            '{}?type=function'.format(self.baseurl),
        ]
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parseCategorys, headers=self.headers)

    def parseCategorys(self, response):
        lst = json.loads(response.body)
        for category in lst["siblingCategories"]:
            product = category["helpdir"].split('/')[-2]
            if (not self.acceptAllCategorys) and (product not in self.acceptCategorys):
                continue
            url = "{}?type=function&product={}".format(self.baseurl, product)
            yield scrapy.Request(url=url, callback=self.parseFuncs, headers=self.headers, meta=dict(product=product))

    def nest(self, data):
        if "child-categories" in data:
            urls = []
            for child in data["child-categories"]:
                urls += self.nest(child)
            return urls
        elif "leaf-items" in data:
            urls = []
            for child in data["leaf-items"]:
                urls.append(self.nest(child))
            return urls
        else:
            assert("path" in data)
            url = "https://www.mathworks.com" + data["path"]
            return url

    def parseFuncs(self, response):
        lst = json.loads(response.body)
        for url in self.nest(lst["category"]):
            yield scrapy.Request(url=url, callback=self.parseFunc, headers=self.headers, meta=response.meta)
    
    def parseFunc(self, response):
        if response.url.startswith('https://www.mathworks.com/login?uri='):
            return
        
        lang = response.xpath('//div[@class="ref_sect"]/h2[text()="Languages"]/..').get()
        if lang:
            self.log("unsupported lang {}, {}".format(pq(lang).text(), response.url), logging.ERROR)
            return

        desc = response.xpath('//div[@class="ref_sect"]/h2[text()="Syntax"]/.. | //div[@class="ref_sect"]/h3[text()="Syntax"]/..').get()
        if not desc:
            self.log("error processing " + response.url, level=logging.ERROR)
            return
        desc_pq = pq(desc)
        desc_pq('h2').remove()
        desc_pq('h3').remove()
        desc:str = desc_pq.text()
        
        title = response.xpath('//span[@class="refname"]/text() | //h1[@itemprop="title"]/text()').get()
        syntaxs = desc.strip().split('\n')
        for syntax in syntaxs:
            prefix = syntax.strip().split('(')[0]
            prefix = prefix.strip().split('=')[-1]
            prefix = prefix.strip().split(' ')[0]
            prefix = prefix.strip()
            if self.prefix_filter.match(prefix) and (prefix.lower() in title.lower() or prefix.lower() in response.url.lower()):
                break
        else:
            self.log("invalid prefix '{}', {}".format(prefix, response.url), level=logging.ERROR)
            return

        name = response.meta.get('product') + "/" + prefix

        elements = response.css('.description_element').getall() or response.xpath('//h2[text()="Description"]/..//span[@itemprop="syntax"]/..').getall()
        if not elements:
            return {
                name: {
                    "prefix": prefix,
                    "body": [
                        prefix
                    ],
                    "description": name + "\n\n" + desc + "\n\nref: " + response.url
                }
            }
        
        paramOpt = []
        plains = []
        opts = None
        for idx, element in enumerate(elements):
            element_pq = pq(element)
            element_pq('.syntax_example').remove()
            syntax = element_pq('span[itemprop="syntax"]').text()
            syntaxParser = FunctionParser(prefix, syntax)
            syntax = syntaxParser.genSyntax()
            if '___' not in syntax:
                plain = syntaxParser.genPlainParams()
                if len(syntaxParser.identifier) > 1 and plain not in plains:
                    paramOpt.append(syntaxParser)
                    plains.append(plain)
            elif len(paramOpt) == 0:
                self.log("___ replace fail on {}".format(response.url), logging.ERROR)
            elif len(paramOpt) == 1:
                syntax = syntax.replace('${___}', paramOpt[0].genParams(), 1)
            else:
                if opts is None:
                    opts = ','.join(set([syn.genPlainParams() for syn in paramOpt]))
                syntax = syntax.replace("${___}", "$0${}1|{}|{}".format('{', opts, "}"), 1)
            syntax = syntax.replace("${...}", "${etc}")
            yield {
                name + ("_{}".format(idx) if idx else ''): {
                    "prefix": prefix,
                    "body": [
                        syntax
                    ],
                    "description": name + "\n\n" + element_pq.text()
                }
            }


    def close(self, reason):
        self.log("closed by {}".format(reason))
        content = None
        with open('funcs.json', 'r') as f:
            content = f.read()
        
        data = json.loads(content)
        funcs = {}
        for func in data:
            for key in func:
                funcs[key] = func[key]
        
        with open('patch.json', 'r') as f:
            funcs.update(json.loads(f.read()))
        
        od = OrderedDict(sorted(funcs.items()))
        with open('snippets.json', 'w') as f:
            f.write(json.dumps(od, indent=4))


if __name__ == "__main__":
    output_json = "funcs.json"
    log_file = "log.txt"
    if os.path.exists(output_json):
        os.remove(output_json)
    if os.path.exists(log_file):
        os.remove(log_file)
    sys.path.append(os.path.dirname(os.path.abspath(__file__))) 
    execute(['scrapy', 'runspider', 'funcs_spider.py', '-o', output_json, '-L', "ERROR", '--logfile', log_file])
