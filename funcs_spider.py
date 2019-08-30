import json
import re
import os
import sys
import logging

import scrapy
from scrapy.cmdline import execute
from pyquery import PyQuery as pq


class FunctionParser(object):
    def __init__(self, syntax):
        self.isFunc = '(' in syntax
        syntax = re.sub(r"(?P<param>\w+)1\s*,?\s*((?P=param)2)?\s*,?\s*((\.+)|(\u2026))\s*,?\s*(?P=param)[nN]", r"\g<param>1_\g<param>N", syntax) # Ellipsis
        if self.isFunc or (syntax.count("=") == 1):
            syntax = re.sub(r".*=\s+(?=[\w.]+\s*(\(|$))", "", syntax) # delete return
        syntax = syntax.replace(",", " ").replace("(", " ").replace(")", "")
        self.identifier = syntax.split()

    def getFname(self):
        return self.identifier[0]

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
    version = "R2019a"
    headers = {
        "User-Agent:": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3879.0 Safari/537.36 Edg/78.0.249.1e"
    }
    baseurl = "https://www.mathworks.com/help/search/reflist/doccenter/en/{}".format(version)
    acceptCategorys = [
        "matlab", # MATLAB
        "simulink", # Simulink
        "5g", # 5G Toolbox
        "aeroblks", # Aerospace Blockset
        "aerotbx", # Aerospace Toolbox
        "antenna", # Antenna Toolbox
        "audio", # Audio Toolbox
        "driving", # Automated Driving Toolbox
        "autosar", # AUTOSAR Blockset
        "bioinfo", # Bioinformatics Toolbox
        "comm", # Communications Toolbox
        "vision", # Computer Vision Toolbox
        "control", # Control System Toolbox
        "curvefit", # Curve Fitting Toolbox
        "daq", # Data Acquisition Toolbox
        "database", # Database Toolbox
        "datafeed", # Datafeed Toolbox
        "deeplearning", # Deep Learning Toolbox
        "qualkitdo", # DO Qualification Kit (for DO-178)
        "dsp", # DSP System Toolbox
        "econ", # Econometrics Toolbox
        "ecoder", # Embedded Coder
        "hdlfilter", # Filter Design HDL Coder
        "fininst", # Financial Instruments Toolbox
        "finance", # Financial Toolbox
        "fixedpoint", # Fixed-Point Designer
        "fuzzy", # Fuzzy Logic Toolbox
        "gads", # Global Optimization Toolbox
        "gpucoder", # GPU Coder
        "hdlcoder", # HDL Coder
        "hdlverifier", # HDL Verifier
        "certkitiec", # IEC Certification Kit (for ISO 26262 and IEC 61508)
        "imaq", # Image Acquisition Toolbox
        "images", # Image Processing Toolbox
        "instrument", # Instrument Control Toolbox
        "ltehdl", # LTE HDL Toolbox
        "lte", # LTE Toolbox
        "map", # Mapping Toolbox
        "coder", # MATLAB Coder
        "compiler", # MATLAB Compiler
        "compiler_sdk", # MATLAB Compiler SDK
        "matlabgrader", # MATLAB Grader
        "matlabmobile_android", # MATLAB Mobile for Android
        "matlabmobile", # MATLAB Mobile for iOS
        "mps", # MATLAB Production Server
        "rptgen", # MATLAB Report Generator
        "mpc", # Model Predictive Control Toolbox
        "mbc", # Model-Based Calibration Toolbox
        "opc", # OPC Toolbox
        "optim", # Optimization Toolbox
        "parallel-computing", # Parallel Computing Toolbox
        "pde", # Partial Differential Equation Toolbox
        "phased", # Phased Array System Toolbox
        "bugfinder", # Polyspace Bug Finder
        "polyspace_bug_finder_access", # Polyspace Bug Finder Access
        "codeprover", # Polyspace Code Prover
        "polyspace_code_prover_access", # Polyspace Code Prover Access
        "autoblks", # Powertrain Blockset
        "predmaint", # Predictive Maintenance Toolbox
        "reinforcement-learning", # Reinforcement Learning Toolbox
        "simrf", # RF Blockset
        "rf", # RF Toolbox
        "risk", # Risk Management Toolbox
        "robotics", # Robotics System Toolbox
        "robust", # Robust Control Toolbox
        "fusion", # Sensor Fusion and Tracking Toolbox
        "serdes", # SerDes Toolbox
        "signal", # Signal Processing Toolbox
        "simbio", # SimBiology
        "simevents", # SimEvents
        "simscape", # Simscape
        "sps", # Simscape Electrical
        "sm", # Simscape Multibody
        "smlink", # Simscape Multibody Link
        "sl3d", # Simulink 3D Animation
        "slcheck", # Simulink Check
        "slci", # Simulink Code Inspector
        "rtw", # Simulink Coder
        "slcontrol", # Simulink Control Design
        "slcoverage", # Simulink Coverage
        "sldo", # Simulink Design Optimization
        "sldv", # Simulink Design Verifier
        "sldrt", # Simulink Desktop Real-Time
        "plccoder", # Simulink PLC Coder
        "xpc", # Simulink Real-Time
        "rptgenext", # Simulink Report Generator
        "slrequirements", # Simulink Requirements
        "sltest", # Simulink Test
        "soc", # SoC Blockset
        "exlink", # Spreadsheet Link
        "stateflow", # Stateflow
        "stats", # Statistics and Machine Learning Toolbox
        "symbolic", # Symbolic Math Toolbox
        "systemcomposer", # System Composer
        "ident", # System Identification Toolbox
        "textanalytics", # Text Analytics Toolbox
        "thingspeak", # ThingSpeak
        "trading", # Trading Toolbox
        "vnt", # Vehicle Network Toolbox
        "visionhdl", # Vision HDL Toolbox
        "wavelet", # Wavelet Toolbox
        "wlan", # WLAN Toolbox
    ]

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
            if product not in self.acceptCategorys:
                continue
            url = "{}?type=function&product={}".format(self.baseurl, product)
            yield scrapy.Request(url=url, callback=self.parseFuncs, headers=self.headers)

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
        # for url in ['https://www.mathworks.com/help/matlab/ref/deval.html']:
            yield scrapy.Request(url=url, callback=self.parseFunc, headers=self.headers)
    
    def parseFunc(self, response):
        body = pq(response.body)
        descriptions = body.find(".description_element > .code_responsive > p")
        paramOpt = []
        plains = []
        opts = None
        for idx, description in enumerate(descriptions):
            descr = pq(description)

            descrText = descr.text()
            syntax = descr.find("span > code.synopsis")
            if len(syntax) == 0:
                continue
            if len(syntax) != 1:
                self.log("num of syntax in a description not equal 1 : " + repr(response.url), logging.ERROR)
                syntax = pq(syntax[0])
            syntax = syntax.text()
            descrText = descrText.replace(syntax, syntax + "\n", 1)

            syntaxParser = FunctionParser(syntax)

            prefix = syntaxParser.getFname() + ('_' + str(idx) if idx != 0 else "")
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
            yield {
                str(prefix): {
                    "prefix": syntaxParser.getFname(),
                    "body": [
                       syntax
                    ],
                    "description": descrText
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
        with open('snippets.json', 'w') as f:
            f.write(json.dumps(funcs, indent=4))


if __name__ == "__main__":
    if os.path.exists("funcs.json"):
        os.remove('funcs.json')
    sys.path.append(os.path.dirname(os.path.abspath(__file__))) 
    execute(['scrapy', 'runspider', 'funcs_spider.py', '-o', 'funcs.json', '-L', "ERROR", '--logfile', 'log.txt'])
