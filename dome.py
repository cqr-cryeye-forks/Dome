#!/usr/bin/env python3


# Created by Vadi (github.com/v4d1)
# Contact me at vadi@securihub.com


from __future__ import print_function  # Python2 compatibility for prints
import socket
import sys
import argparse
import requests
import re
import os
import uuid
import random
import json
import time
import pathlib

from dns import resolver
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait
from datetime import datetime

from paths import CONFIG_PATH, WORDLIST_PATH

subdomains_found = {}
subdomains_found_list = []
wildcardsDicc = {}
wildcard = False
mode = "passive"
apis = {}
portsPassive = {}
noExists = []
count = 0
countToChange = 0
isWebArchive = False
res = resolver.Resolver()

# resolvers = ['1.1.1.1'] #Cloudfare resolver, actually the fastest one

resolvers = ['1.1.1.1', '9.9.9.9', '8.8.8.8', '1.0.0.1', '208.67.222.222', '8.8.4.4', '149.112.112.11']


def changeDNS():  # Not used right now

    global resolvers
    global res

    resolvers.append(resolvers.pop(0))  # first resolver is now the last
    res.nameservers = [resolvers[0]]


def banner(version):
    if printOutput: print(
        Y + "\n     _                 _____ \n    | |               |  ___|\n  __| | ___  _ __ ___ | |__  \n / _` |/ _ \| '_ ` _ \|  __| \n| (_| | (_) | | | | | | |___ \n \__,_|\___/|_| |_| |_\____/" + R + "   by vadi @ securihub.com\n\t\t\t\tv" + version + "\n" + W)


def color(no_color):
    # Thanks aboul3la
    global G, Y, B, R, W

    if no_color == False:
        is_windows = sys.platform.startswith('win')

        G = '\033[92m'  # green
        Y = '\033[93m'  # yellow
        B = '\033[94m'  # blue
        R = '\033[91m'  # red
        W = '\033[0m'  # white

        # Console Colors
        if is_windows:
            try:
                import win_unicode_console, colorama
                win_unicode_console.enable()
                colorama.init()
            except:
                if printOutput:
                    print("To use colored version in Windows: 'pip install win_unicode_console colorama'")
                    print("You can use --no-color to use non colored output")
    else:
        G = Y = B = R = W = ''


def parser_error(errmsg):
    color(True)
    print(
        Y + "\n     _                 _____ \n    | |               |  ___|\n  __| | ___  _ __ ___ | |__  \n / _` |/ _ \| '_ ` _ \|  __| \n| (_| | (_) | | | | | | |___ \n \__,_|\___/|_| |_| |_\____/" + R + "   by vadi @ securihub.com\n\n" + W)
    print("Usage: python3 " + sys.argv[0] + " [Options] use -h for help")
    print(R + "Error: " + errmsg + W)
    sys.exit()


def parse_args():
    parser = argparse.ArgumentParser(epilog='\tExample: \r\npython ' + sys.argv[
        0] + " -m active -d hackerone.com -w subdomains-5000.txt -p 80,443,8080 -o")
    parser._optionals.title = "OPTIONS"
    parser.error = parser_error
    parser.add_argument('-m', '--mode', help="Scan mode. Active or passive", required=True)
    parser.add_argument('-d', '--domain', help="Domains name to enumerate subdomains (Separated by commas)",
                        required=True)
    parser.add_argument('-w', '--wordlist', action='store_true', help='Wordlist containing subdomain prefix to bruteforce')
    parser.add_argument('-p', '--ports', help='Scan the subdomains found against specified tcp ports.')
    parser.add_argument('-i', '--ip', help='When a subdomain is found, show the ip too', action='store_true')

    parser.add_argument('-nb', '--no-bruteforce', help='Dont make pure bruteforce up to 3 letters', action='store_true')
    parser.add_argument('--top-100-ports', help='Scan the top 100 ports of the subdomain.', action='store_true')
    parser.add_argument('--top-1000-ports', help='Scan the top 1000 ports of the subdomain.', action='store_true')
    parser.add_argument('--top-web-ports', help='Scan the top web ports of the subdomain.', action='store_true')

    parser.add_argument('-s', '--silent', help='Silent mode. No output in terminal', action='store_false')
    parser.add_argument('--no-color', help='Dont print colored output', action='store_true')
    parser.add_argument('-t', '--threads', help='Number of threads to use', type=int, default=25)

    parser.add_argument('-o', '--output', help='Save the results json file', action='store_true')
    parser.add_argument('--output-file', help='Save the results json file', required=True)

    parser.add_argument('--max-response-size', help='Maximun length for HTTP response', type=int, default=5000000)
    parser.add_argument('--no-passive', help='Do not use OSINT techniques to obtain valid subdomains',
                        action='store_false')
    parser.add_argument('-r', '--resolvers', help='Textfile with DNS resolvers to use. One per line')
    parser.add_argument('--version', help='Show dome version and exit', action='store_true')
    parser.add_argument('-v', '--verbose', help='Show more information during execution', action='store_true')

    return parser.parse_args()


def checkDomain(domain):
    if domain.startswith((".", "*", "_")):
        return

    if domain in noExists:  # This is used to avoid overload in web archive (Web Archive can extract same domain thousands of times)
        return

    # If the subdomain was tested before, it wont be scanned again. This is critical to reduce overload
    if domain not in subdomains_found_list:
        rootdomain = domain.split('.')[-2] + "." + domain.split('.')[-1]  # DONT WORK WITH DOMAINS LIKE domain.gov.uk

        if domain == rootdomain:  # we dont test de domain itself
            return

        # If passive mode is selected, we dont have ip info so we use "no_ip_because_of_passive_mode"
        ips = ["no_ip_because_of_passive_mode"]

        # In active mode, the subdomain is tested to determine if it is alive or not
        if mode.lower() == "active":
            try:
                global count
                count = count + 1

                start = time.time()

                # ip_result = socket.gethostbyname(domain)
                res.timeout = 1
                res.lifetime = 1
                answers = res.resolve(domain)

                ip_result = answers[0].address
                ips = []
                for rdata in answers:
                    ips.append(rdata.address)

                # We check if ip correspond to a wildcard DNS
                if wildcardsDicc:
                    for d in wildcardsDicc.keys():
                        if d == rootdomain:
                            if ip_result in wildcardsDicc[rootdomain]:
                                return
            except:
                if len(resolvers) > 1:  # If we are using a list of resolvers, the queue will change every 50 requests of >5 secs
                    global countToChange
                    end = time.time()
                    if end - start > 5:
                        countToChange = countToChange + 1
                    if countToChange > 50 and res.nameservers[0] == resolvers[
                        0]:  # If 50 subdomains take longer than 5 secs to resolve, we call changeDNS to change the ip of DNS resolver
                        changeDNS()
                        countToChange = 0

                if isWebArchive:
                    noExists.append(
                        domain)  # We need to storage when a domain doesn't exists in order to not overload the server (web archive module can make so much requests with same domain)
                return

        # If no exception is given, the ip exists so we create the dictionary as follows {"1.1.1.1": ["subdomain1", "subdomain2"]}
        if show_ip == True and mode.lower() == "active":
            if printOutput: print(G + "[+] Found new: " + domain + " at " + W + ', '.join(ips) + "\n", end='\r')
        else:
            if printOutput: print(G + "[+] Found new: " + domain)

        for singleip in ips:

            found = False
            if rootdomain not in list(subdomains_found.keys()):

                subdomains_found[rootdomain] = [{singleip: [
                    domain]}]  # If domain dont exists, it creates {"domain": [{"ip":["subdomain1",...]}, ...]}

            else:

                count2 = 0
                for i in range(len(subdomains_found[rootdomain])):  # if ip is in diccionary
                    count2 = count2 + 1
                    if singleip in list(
                            subdomains_found[rootdomain][i].keys()):  # First time = assing, next times = append
                        if domain not in subdomains_found[rootdomain][i][singleip]:
                            subdomains_found[rootdomain][i][singleip].append(domain)
                            found = True
                            break

                if count2 == len(subdomains_found[rootdomain]) and found == False:  # if ip doesnt exists...
                    subdomains_found[rootdomain].append({singleip: [domain]})

        subdomains_found_list.append(domain)

        return True


def brute(domains, entries, option):
    # domains can be a list if user input more than one domain or recursively is True
    for domain in domains:
        for entry in entries:
            subdomain = entry.strip() + "." + domain
            checkDomain(subdomain)
            print(entry)
    return


def openPorts(ips, ports, timeout):
    for ip in ips:
        port_open = []
        for port in ports:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            try:
                s.connect((ip, port))
                port_open.append(port)
            except Exception as e:
                pass
            finally:
                s.close()

        for domain in list(subdomains_found.keys()):  # For every domain...
            for i in range(len(subdomains_found[domain])):
                if ip == list(subdomains_found[domain][i].keys())[0]:  # For every ip in domain...
                    if len(port_open) > 0:
                        if printOutput: print(G + ip + " " + str(subdomains_found[domain][i][ip]) + " " + Y + str(
                            port_open))  # If we found the ip, we append the open ports
                    else:
                        if printOutput: print(G + ip + " " + str(subdomains_found[domain][i][
                                                                     ip]) + " " + Y + "No open ports")  # If we found the ip, we append the open ports
                    subdomains_found[domain][i][ip].append(port_open)

# I'm not using PureBrute because we have huge wordlist for runWordlistBrute, it's more effective.
# def runPureBrute(domains, threads):
#     charset = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u',
#                'v', 'w', 'x', 'y', 'z']
#
#     entries = []
#
#     for letter1 in charset:
#         entries.append(letter1)
#         for letter2 in charset:
#             entries.append(letter1 + letter2)
#             for letter3 in charset:
#                 entries.append(letter1 + letter2 + letter3)
#
#     if printOutputV: print(B + "[!] Bruteforcing from " + W + "a" + B + " to" + W + " zzz: ")
#
#     # We split the wordlist in N parts (N = number of threads)
#     x = int(len(entries) / threads) + 1
#     splited_list = [entries[i:i + x] for i in range(0, len(entries), x)]
#     # splited_list = np.array_split(entries, threads)
#
#     executor = ThreadPoolExecutor(max_workers=threads)
#     futures = [executor.submit(brute, domains, splited_list[i], 1) for i in range(len(splited_list))]
#     wait(futures)


def runWordlistBrute(domains, entries, threads):
    # if printOutputV: print(B + "[!] Bruteforcing with wordlist: " + W + wordlist_name + G)
    print("[!] Bruteforcing with wordlist")
    # We split the wordlist in N parts (N = number of threads)

    x = int(len(entries) / threads) + 1
    splited_list = [entries[i:i + x] for i in range(0, len(entries), x)]
    # splited_list = np.array_split(entries, threads)

    executor = ThreadPoolExecutor(max_workers=threads)
    futures = [executor.submit(brute, domains, splited_list[i], 2) for i in range(len(splited_list))]
    wait(futures)


def checkCommonPrefix():
    commonPrefix = ['-staging', '-testing', '-pre', '-sts', '-test', '-stage']
    for subdomain in subdomains_found_list:
        for c in commonPrefix:
            idx = subdomain.index(".")
            new = subdomain[:idx] + c + subdomain[idx:]
            checkDomain(new)


def runOpenPorts(threads, ports):
    timeout = 0.25  # increase if the hosts take longer to respond
    ips_to_scan = []

    for key in list(subdomains_found.keys()):
        for i in range(len(subdomains_found[key])):
            ips_to_scan.append(
                list(subdomains_found[key][i].keys())[0])  # This iterates all dicc extracting all ip addresses

    if len(ips_to_scan) == 0:
        return

    if printOutput: print(B + "[!] Checking open ports:                ")

    executor = ThreadPoolExecutor(max_workers=threads)

    if (len(ips_to_scan) < threads):

        splited_list = [ips_to_scan[i:i + 1] for i in range(0, len(ips_to_scan), 1)]

        futures = [executor.submit(openPorts, splited_list[i], ports, timeout) for i in range(len(ips_to_scan))]
    else:

        x = int(len(ips_to_scan) / threads) + 1

        splited_list = [ips_to_scan[i:i + x] for i in range(0, len(ips_to_scan), x)]

        futures = [executor.submit(openPorts, splited_list[i], ports, timeout) for i in range(len(splited_list))]

    wait(futures)


# OSINT TECHNIQUES


def runOpenPortsPassive():
    if printOutput: print(B + "\n[!] Checking open ports passively: ")
    for i in range(len(list(portsPassive.keys()))):
        subdomain = list(portsPassive.keys())[i]
        if printOutput: print(G + subdomain + " " + Y + str(portsPassive[subdomain]))


def runCrt(domain):
    if printOutputV: print(B + "\n[!] Searching in" + W + " Crt.sh:")

    if printOutputV: print(G + "[+] Downloading data")
    r = requests.get("https://crt.sh/?q=" + domain + "&output=json")
    if printOutputV: print(G + "[+] Downloaded data for " + W + domain + " (" + str(len(r.text) / 1000000) + "MB)")
    if len(r.text) > max_response:
        if printOutputV: print(W + "[-] HTTP response to high to grep. Length is " + R + str(
            len(r.text)) + W + " and max_response is " + R + str(
            max_response) + W + ". Add --max-response-size [NUMBER] to increase maximum response size.")
    else:
        pattern = '"[a-zA-Z0-9\-\.]*\.' + str(domain.split('.')[0]) + '\.' + str(domain.split('.')[1])
        for domain in re.findall(pattern, r.text):
            checkDomain(domain.split("\"")[1])  # we send to check domain to verify it still exists


def runWebArchive(domain):
    if printOutputV: print(
        B + "\n[!] Searching in" + W + " Web Archive: " + B + "this web page can take longer to load.")

    if printOutputV: print(G + "[+] Downloading data")

    try:
        r = requests.get(
            "https://web.archive.org/cdx/search/cdx?url=*." + domain + "&output=txt&fl=original&collapse=urlkey&page=",
            timeout=10)
    except:
        if printOutputV: print("Timeout exceeded. Exiting")
        return

    if printOutputV: print(G + "[+] Downloaded data for " + W + domain + " (" + str(len(r.text) / 1000000) + "MB)")
    len_res = len(r.text)
    if len_res > max_response:
        if printOutputV: print(W + "[-] HTTP response to high to grep. Length is " + R + str(
            len(r.text)) + W + " and max_response is " + R + str(
            max_response) + W + ". Add --max-response-size [NUMBER] to increase maximum response size.")
    else:
        pattern = '(?!2?F)[a-zA-Z0-9\-\.]*\.' + str(domain.split('.')[0]) + '\.' + str(domain.split('.')[1])
        if len_res > 5000000:
            if printOutputV: print(G + "[+] Greping file. This can take a while\n")

        for domain in re.findall(pattern, r.text):
            checkDomain(domain)  # we send to check domain to verify it still exists


def runSecurityTrails(domain):
    if printOutputV: print(B + "\n[!] Searching in" + W + " SecurityTrails:")
    r = requests.get(
        "https://api.securitytrails.com/v1/domain/" + domain + "/subdomains?apikey=" + apis["SECURITYTRAILS"])
    if r.status_code == 429:
        if printOutputV: print(R + "\n[-] API Limit exceeded. Free API only have 50 requests/month.")
        return
    if "subdomains" not in r.text:
        if printOutputV: print(R + "\n[-] Error with API. Free API only have 50 requests/month. Response: " + r.text)
        return
    d = json.loads(r.text)
    for subdomain in d["subdomains"]:
        checkDomain(subdomain + "." + domain)


def runPassiveTotal(domain):
    if printOutputV: print(B + "\n[!] Searching in" + W + " PassiveTotal:")

    auth = (apis["PASSIVETOTAL_USERNAME"], apis["PASSIVETOTAL"])

    r = requests.get("https://api.riskiq.net/pt/v2/account/quota", auth=auth)
    d = json.loads(r.text)
    req = d["user"]["licenseCounts"]["searchApi"]
    limit = d["user"]["licenseLimits"]["searchApi"]
    if printOutputV: print(
        G + "[!] " + W + str(limit - req) + G + " requests available of " + str(limit) + " (per month)\n")
    if (req == limit):
        if printOutputV: print(R + "[-] No API requests left this month")
        return

    r = requests.get("https://api.passivetotal.org/v2/enrichment/subdomains?query=" + domain, auth=auth)
    d = json.loads(r.text)
    for subdomain in d["subdomains"]:
        checkDomain(subdomain + "." + domain)


def runSpyse(domain):
    if printOutputV: print(B + "\n[!] Searching in" + W + " Spyse:")

    header = {"Authorization": "Bearer " + apis["SPYSE"], "Accept": "application/json"}

    r = requests.get("https://api.spyse.com/v4/data/account/quota", headers=header)
    d = json.loads(r.text)
    req_remaining = d["data"]["items"][0]["api_requests_remaining"]
    limit = d["data"]["items"][0]["api_requests_limit"]

    if printOutputV: print(
        G + "[!] " + W + str(req_remaining) + G + " requests available of " + str(limit) + " (per month)")
    if (req_remaining == 0):
        if printOutputV: print(R + "[-] No API requests left this month")
        return

    r = requests.post("https://api.spyse.com/v4/data/domain/search", headers=header,
                      data="{\"search_params\":[{\"name\":{\"operator\":\"ends\",\"value\":\"." + domain + "\"}}],\"limit\":100}")
    # d = json.loads(r.text)
    if len(r.text) > max_response:
        if printOutputV: print(W + "[-] HTTP response to high to grep. Length is " + R + str(
            len(r.text)) + W + " and max_response is " + R + str(
            max_response) + W + ". Add --max-response-size [NUMBER] to increase maximum response size.")
    else:
        pattern = '(?!2?F)[a-zA-Z0-9\-\.]*\.' + str(domain.split('.')[0]) + '\.' + str(domain.split('.')[1])
        for domain in re.findall(pattern, r.text):
            checkDomain(domain)  # we send to check domain to verify it still exists


def runCertSpotter(domain):
    if printOutputV: print(B + "\n[!] Searching in" + W + " CertSpotter:\n" + G + "[!] Free 100/queries per hour")

    header = {}
    if apis:
        for apiengines in apis.keys():
            if apiengines == "CERTSPOTTER":
                if printOutputV: print(G + "[+] CertSpotter API Key found\n")
                header = {"Authorization": "Bearer " + apis["CERTSPOTTER"]}

    r = requests.get(
        "https://api.certspotter.com/v1/issuances?domain=" + domain + "&include_subdomains=true&expand=dns_names&expand=issuer&expand=cert",
        headers=header)

    if "You have exceeded the domain" in r.text:
        if printOutputV: print(R + "\n[-] Rate exceeded. Wait some minutes")
        return
    if len(r.text) > max_response:
        if printOutputV: print(W + "[-] HTTP response to high to grep. Length is " + R + str(
            len(r.text)) + W + " and max_response is " + R + str(
            max_response) + W + ". Add --max-response-size [NUMBER] to increase maximum response size.")
    else:
        pattern = '(?!2?F)[a-zA-Z0-9\-\.]*\.' + str(domain.split('.')[0]) + '\.' + str(domain.split('.')[1])
        for domain in re.findall(pattern, r.text):
            checkDomain(domain)  # we send to check domain to verify it still exists


def runShodan(domain):
    if printOutputV: print(B + "\n[!] Searching in" + W + " Shodan:")
    r = requests.get('https://api.shodan.io/dns/domain/' + domain + '?key=' + apis["SHODAN"])
    d = json.loads(r.text)
    for i in range(len(d["data"])):
        subd = d["data"][i]["subdomain"]
        if subd != '' and '*' not in subd:
            if "ports" in d["data"][i].keys():
                portsPassive[subd + "." + domain] = d["data"][i]["ports"]
            checkDomain(subd + "." + domain)


def runBinaryEdge(domain):
    if printOutputV: print(B + "\n[!] Searching in" + W + " BinaryEdge:")
    header = {"X-Key": apis["BINARYEDGE"]}

    r = requests.get("https://api.binaryedge.io/v2/user/subscription", headers=header)
    d = json.loads(r.text)
    if printOutputV: print(G + "[!] " + W + str(d["requests_left"]) + G + " requests available of " + W + str(
        d["requests_plan"]) + G + " (per month)\n")
    if (d["requests_left"] == 0):
        if printOutputV: print(R + "[-] No API requests left this month" + B)
        return

    flag = True
    page = 1
    while flag == True:
        r = requests.get("https://api.binaryedge.io/v2/query/domains/subdomain/" + domain + "?page=" + str(page),
                         headers=header)
        d = json.loads(r.text)

        if len(r.text) > max_response:
            if printOutputV: print(W + "[-] HTTP response to high to grep. Length is " + R + str(
                len(r.text)) + W + " and max_response is " + R + str(
                max_response) + W + ". Add --max-response-size [NUMBER] to increase maximum response size.")
        else:
            for subdomain in d["events"]:
                checkDomain(subdomain)  # we send to check domain to verify it still exists
        if (page * 100 > d["total"]):  # We iterate pages until end
            flag = False
        page = page + 1


def runAlienVault(domain):
    if printOutputV: print(B + "\n[!] Searching in" + W + " AlienVault:")

    r = requests.get("https://otx.alienvault.com/api/v1/indicators/domain/" + domain + "/passive_dns")
    d = json.loads(r.text)
    for i in range(len(d["passive_dns"])):
        if domain in d["passive_dns"][i]["hostname"]:
            checkDomain(d["passive_dns"][i]["hostname"])


def runSiteDossier(domain):
    if printOutputV: print(B + "\n[!] Searching in" + W + " Sitedossier:")
    data = ""
    page = 1
    while "No data currently available." not in data:
        r = requests.get("http://www.sitedossier.com/parentdomain/" + domain + "/" + str(page))
        if "your IP has been blacklisted" in r.text:
            if printOutputV: print(R + "[-] Your IP has been blacklisted")
            return
        page = page + 100
        data = r.text
        pattern = '(?!2?F)[a-zA-Z0-9\-\.]*\.' + str(domain.split('.')[0]) + '\.' + str(domain.split('.')[1])
        for domain in re.findall(pattern, r.text):
            checkDomain(domain)  # we send to check domain to verify it still exists


# This function is used as template. Makes request method and grep
def defaultRun(name, request, domain):
    if printOutputV: print(B + "\n[!] Searching in" + W + " " + name + ":")
    r = requests.get(request)
    if name == "VirusTotal":
        if r.status_code == 429:
            if printOutputV: print(
                R + "\n[-] API Limit exceeded. The Public API is limited to 500 requests per day and a rate of 4 requests per minute." + B)
            return
    if len(r.text) > max_response:
        if printOutputV: print(W + "[-] HTTP response to high to grep. Length is " + R + str(
            len(r.text)) + W + " and max_response is " + R + str(
            max_response) + W + ". Add --max-response-size [NUMBER] to increase maximum response size.")
    else:
        pattern = '(?!2?F)[a-zA-Z0-9\-\.]*\.' + str(domain.split('.')[0]) + '\.' + str(domain.split('.')[1])
        for domain in re.findall(pattern, r.text):
            checkDomain(domain)  # we send to check domain to verify it still exists


def runPassive(domains):
    if printOutput: print(B + "[+] Running passive mode:")

    importApis()
    try:  # Try catch needed in case a web page block our requests

        if not apis:
            if printOutput: print(Y + "[!] No API Tokens detected. Running free OSINT engines...")

        for domain in domains:

            defaultRun("Sonar", "https://sonar.omnisint.io/subdomains/" + domain + "?page=", domain)
            defaultRun("Hunt.io", "https://fullhunt.io/api/v1/domain/" + domain + "/details", domain)
            defaultRun("Anubis-DB", "https://jonlu.ca/anubis/subdomains/" + domain, domain)
            defaultRun("ThreatCrowd", "https://www.threatcrowd.org/searchApi/v2/domain/report/?domain=" + domain,
                       domain)
            defaultRun("HackerTarget", "https://api.hackertarget.com/hostsearch/?q=" + domain, domain)
            defaultRun("RapidDNS", "https://rapiddns.io/subdomain/" + domain + "?full=1&down=1", domain)
            defaultRun("ThreatMiner", "https://api.threatminer.org/v2/domain.php?q=" + domain + "&rt=5", domain)
            defaultRun("UrlScan.io", "https://urlscan.io/api/v1/search/?q=" + domain, domain)
            defaultRun("BufferOverflow", "https://dns.bufferover.run/dns?q=" + domain, domain)
            defaultRun("DNS Repo", "https://dnsrepo.noc.org/?search=." + domain, domain)

            runSiteDossier(domain)
            runAlienVault(domain)
            global isWebArchive
            isWebArchive == True
            runWebArchive(
                domain)  # We use flag to tell function checkDomain to store the non existing subdomains due to high overload
            isWebArchive == False
            runCertSpotter(
                domain)  # CertSpotter can be used with api or without, so we make the condition inside the function
            runCrt(domain)

            if apis:

                for api in apis.keys():
                    if api == "VIRUSTOTAL":
                        defaultRun("VirusTotal", "https://www.virustotal.com/vtapi/v2/domain/report?apikey=" + apis[
                            "VIRUSTOTAL"] + "&domain=" + domain, domain)
                    elif api == "SHODAN":
                        runShodan(domain)
                    elif api == "SPYSE":
                        runSpyse(domain)
                    elif api == "SECURITYTRAILS":
                        runSecurityTrails(domain)
                    elif api == "PASSIVETOTAL":
                        runPassiveTotal(domain)
                    elif api == "BINARYEDGE":
                        runBinaryEdge(domain)
    except:
        pass


def runActive(domains, entries, threads, no_bruteforce):
    if printOutput: print(B + "\n[+] Running active mode: ")
    # if not no_bruteforce: runPureBrute(domains, threads)
    if len(entries) > 0:
        runWordlistBrute(domains, entries, threads)
    else:
        if printOutput: print(R + "\n\n[-] No wordlist provided. ")

    checkCommonPrefix()


def checkWildcard(domains):
    ips = []

    for domain in domains:
        if printOutput: print(B + "\n[!] Checking if " + W + domain + B + " has wildcard enable")
        count = 0
        # We generate 10 random and non existing subdomains and we test if they are marked as up. If all subdomains "exists", the domain has wildcard enable
        for i in range(5):
            try:
                x = uuid.uuid4().hex[0:random.randint(6, 32)]
                # ip = socket.gethostbyname(x +"."+ domain)
                answers = res.resolve(x + "." + domain)
                ip = answers[0].address
                if ip not in ips:
                    ips.append(ip)
                count = count + 1
            except:
                pass

        if (count == 5):
            if printOutput: print(
                R + "\n[-] Alert: Wildcard enable for domain " + domain + ". Omiting subdomains that resolve for " + str(
                    ips))
            wildcardsDicc[domain] = ips  # Store the ip to discard subdomains with this ip
        else:
            if printOutput: print(G + "[+] No wildcard enable for " + W + domain)


def output(output_file, mode_info):

    if printOutput: print(B + "[+] Writing output in " + W + "results folder")

    content = subdomains_found
    final_data = {}
    if mode_info == "active":
        new_data = []
        if content:
            key = list(content.keys())[0]

            for item in content[key]:
                for sub_key, value in item.items():
                    hosts = [item for item in value if not isinstance(item, list)]
                    ports = [item for item in value if isinstance(item, list)]

                    if ports:
                        ports = ports[0]

                    new_entry = {
                        "ip": sub_key,
                        "hosts": hosts,
                        "ports": ports
                    }
                    new_data.append(new_entry)

        final_data = {"active_mode": new_data}

    elif mode_info == "passive":
        new_data = []
        if content:
            for domain, items in content.items():
                for item in items:
                    for sub_key, hosts in item.items():
                        if sub_key == 'no_ip_because_of_passive_mode':
                            for host in hosts:
                                new_data.append({"host": host})

        final_data = {"passive_mode": new_data}

    root_path = pathlib.Path(__file__).parent
    file_path = root_path.joinpath(output_file)
    file_path.write_text(json.dumps(final_data))


def importApis():
    if not CONFIG_PATH.exists():
        if printOutput: print(Y + "\n[!] File config.api not found in current directory")
        return
    else:
        print("Config file found")

    config_file = CONFIG_PATH.read_text()
    for line in config_file.splitlines():
        if not line.startswith('#'):  # Delete comments
            line = line.strip()
            if line != '':  # Delete empty lines
                line.split("=")
                if line.split("=")[1] != '""':  # If api
                    apis[line.split("=")[0]] = line.split("=")[1].replace('"', '')


if __name__ == "__main__":
    args = parse_args()

    version = "1.1"
    # TO BE IMPLEMENTED AUTO UPDATE

    global printOutput
    global max_response
    global wordlist_name
    global show_ip

    printOutput = args.silent
    printOutputV = args.silent and args.verbose
    outputFlag = args.output
    output_file = args.output_file

    color(args.no_color)
    banner(version)

    # if not printOutput and not outputFlag:
    # 	#If --silent is selected, check that --output option is selected too, otherwise the execution has no sense
    # 	print(R + "\n[-] Error, if you use silent mode, you need to specify output flag")
    # 	exit()
    #
    # #Prints current version and exits
    # if (args.version):
    # 	print(G + "[+] Current version: " + Y + version)
    # 	exit()

    # Internet connection test
    try:
        socket.gethostbyname('google.com')
    except:
        print(R + "[-] No internet connection.")
        exit()

    wordlist_name = WORDLIST_PATH
    if wordlist_name:
        if not os.path.exists(wordlist_name):
            print(
                R + "Wordlist file '" + wordlist_name + "' does not exists. Create it or run without -w,--wordlist to do not perform wordlist based attack.")
            exit()

    max_response = args.max_response_size
    domains = args.domain.split(',')
    threads = args.threads
    mode = args.mode.lower()
    show_ip = args.ip

    args.resolvers
    if args.resolvers:
        if not os.path.exists(args.resolvers):
            print(
                R + "Resolvers file '" + args.resolvers + "' does not exists. Create it or run without -r,--resolvers flags")
            exit()
        file = open(args.resolvers, 'r')
        res.nameservers = file.read().splitlines()
        file.close()
    else:
        res.nameservers = resolvers

    if mode != "passive" and mode != "active":
        if printOutput: print(R + "\n[-] Error mode. Mode argument only accepts 'active' or 'passive'")
        exit()

    if args.ports:
        ports = args.ports.split(',')

    topWebports = [80, 81, 88, 443, 8080, 8443, 8888]
    top100ports = [7, 9, 13, 21, 22, 23, 25, 26, 37, 53, 79, 80, 81, 88, 106, 110, 111, 113, 119, 135, 139, 143, 144,
                   179, 199, 389, 427, 443, 444, 445, 465, 513514, 515, 543, 544, 548, 554, 587, 631, 646, 873, 990,
                   993, 995, 1025, 1026, 1027, 1028, 1029, 1110, 1433, 1720, 1723, 1755, 1900, 2000, 2001, 2049, 2121,
                   2717, 3000, 3128, 3306, 3389, 3986, 4899, 5000, 5009, 5051, 5060, 5101, 5190, 5357, 5432, 5631, 5666,
                   5800, 5900, 6000, 6001, 6646, 7070, 8000, 8008, 8009, 8080, 8081, 8443, 8888, 9100, 9999, 10000,
                   32768, 49152, 49153, 49154, 49155, 49156, 49157]
    top1000ports = [1, 3, 4, 6, 7, 9, 13, 17, 19, 20, 21, 22, 23, 24, 25, 26, 30, 32, 33, 37, 42, 43, 49, 53, 70, 79,
                    80, 81, 82, 83, 84, 85, 88, 89, 90, 99, 100, 106, 109, 110, 111, 113, 119, 125, 135, 139, 143, 144,
                    146, 161, 163, 179, 199, 211, 212, 222, 254, 255, 256, 259, 264, 280, 301, 306, 311, 340, 366, 389,
                    406, 407, 416, 417, 425, 427, 443, 444, 445, 458, 464, 465, 481, 497, 500, 512, 513, 514, 515, 524,
                    541, 543, 544, 545, 548, 554, 555, 563, 587, 593, 616, 617, 625, 631, 636, 646, 648, 666, 667, 668,
                    683, 687, 691, 700, 705, 711, 714, 720, 722, 726, 749, 765, 777, 783, 787, 800, 801, 808, 843, 873,
                    880, 888, 898, 900, 901, 902, 903, 911, 912, 981, 987, 990, 992, 993, 995, 999, 1000, 1001, 1002,
                    1007, 1009, 1010, 1011, 1021, 1022, 1023, 1024, 1025, 1026, 1027, 1028, 1029, 1030, 1031, 1032,
                    1033, 1034, 1035, 1036, 1037, 1038, 1039, 1040, 1041, 1042, 1043, 1044, 1045, 1046, 1047, 1048,
                    1049, 1050, 1051, 1052, 1053, 1054, 1055, 1056, 1057, 1058, 1059, 1060, 1061, 1062, 1063, 1064,
                    1065, 1066, 1067, 1068, 1069, 1070, 1071, 1072, 1073, 1074, 1075, 1076, 1077, 1078, 1079, 1080,
                    1081, 1082, 1083, 1084, 1085, 1086, 1087, 1088, 1089, 1090, 1091, 1092, 1093, 1094, 1095, 1096,
                    1097, 1098, 1099, 1100, 1102, 1104, 1105, 1106, 1107, 1108, 1110, 1111, 1112, 1113, 1114, 1117,
                    1119, 1121, 1122, 1123, 1124, 1126, 1130, 1131, 1132, 1137, 1138, 1141, 1145, 1147, 1148, 1149,
                    1151, 1152, 1154, 1163, 1164, 1165, 1166, 1169, 1174, 1175, 1183, 1185, 1186, 1187, 1192, 1198,
                    1199, 1201, 1213, 1216, 1217, 1218, 1233, 1234, 1236, 1244, 1247, 1248, 1259, 1271, 1272, 1277,
                    1287, 1296, 1300, 1301, 1309, 1310, 1311, 1322, 1328, 1334, 1352, 1417, 1433, 1434, 1443, 1455,
                    1461, 1494, 1500, 1501, 1503, 1521, 1524, 1533, 1556, 1580, 1583, 1594, 1600, 1641, 1658, 1666,
                    1687, 1688, 1700, 1717, 1718, 1719, 1720, 1721, 1723, 1755, 1761, 1782, 1783, 1801, 1805, 1812,
                    1839, 1840, 1862, 1863, 1864, 1875, 1900, 1914, 1935, 1947, 1971, 1972, 1974, 1984, 1998, 1999,
                    2010, 2013, 2020, 2021, 2022, 2030, 2033, 2034, 2035, 2038, 2040, 2041, 2042, 2043, 2045, 2046,
                    2047, 2048, 2049, 2065, 2068, 2099, 2100, 2103, 2105, 2106, 2107, 2111, 2119, 2121, 2126, 2135,
                    2144, 2160, 2161, 2170, 2179, 2190, 2191, 2196, 2200, 2222, 2251, 2260, 2288, 2301, 2323, 2366,
                    2381, 2382, 2383, 2393, 2394, 2399, 2401, 2492, 2500, 2522, 2525, 2557, 2601, 2602, 2604, 2605,
                    2607, 2608, 2638, 2701, 2702, 2710, 2717, 2718, 2725, 2800, 2809, 2811, 2869, 2875, 2909, 2910,
                    2920, 2967, 2968, 2998, 3000, 3001, 3003, 3005, 3006, 3007, 3011, 3013, 3017, 3030, 3031, 3052,
                    3071, 3077, 3128, 3168, 3211, 3221, 3260, 3261, 3268, 3269, 3283, 3300, 3301, 3306, 3322, 3323,
                    3324, 3325, 3333, 3351, 3367, 3369, 3370, 3371, 3372, 3389, 3390, 3404, 3476, 3493, 3517, 3527,
                    3546, 3551, 3580, 3659, 3689, 3690, 3703, 3737, 3766, 3784, 3800, 3801, 3809, 3814, 3826, 3827,
                    3828, 3851, 3869, 3871, 3878, 3880, 3889, 3905, 3914, 3918, 3920, 3945, 3971, 3986, 3995, 3998,
                    4000, 4001, 4002, 4003, 4004, 4005, 4006, 4045, 4111, 4125, 4126, 4129, 4224, 4242, 4279, 4321,
                    4343, 4443, 4444, 4445, 4446, 4449, 4550, 4567, 4662, 4848, 4899, 4900, 4998, 5000, 5001, 5002,
                    5003, 5004, 5009, 5030, 5033, 5050, 5051, 5054, 5060, 5061, 5080, 5087, 5100, 5101, 5102, 5120,
                    5190, 5200, 5214, 5221, 5222, 5225, 5226, 5269, 5280, 5298, 5357, 5405, 5414, 5431, 5432, 5440,
                    5500, 5510, 5544, 5550, 5555, 5560, 5566, 5631, 5633, 5666, 5678, 5679, 5718, 5730, 5800, 5801,
                    5802, 5810, 5811, 5815, 5822, 5825, 5850, 5859, 5862, 5877, 5900, 5901, 5902, 5903, 5904, 5906,
                    5907, 5910, 5911, 5915, 5922, 5925, 5950, 5952, 5959, 5960, 5961, 5962, 5963, 5987, 5988, 5989,
                    5998, 5999, 6000, 6001, 6002, 6003, 6004, 6005, 6006, 6007, 6009, 6025, 6059, 6100, 6101, 6106,
                    6112, 6123, 6129, 6156, 6346, 6389, 6502, 6510, 6543, 6547, 6565, 6566, 6567, 6580, 6646, 6666,
                    6667, 6668, 6669, 6689, 6692, 6699, 6779, 6788, 6789, 6792, 6839, 6881, 6901, 6969, 7000, 7001,
                    7002, 7004, 7007, 7019, 7025, 7070, 7100, 7103, 7106, 7200, 7201, 7402, 7435, 7443, 7496, 7512,
                    7625, 7627, 7676, 7741, 7777, 7778, 7800, 7911, 7920, 7921, 7937, 7938, 7999, 8000, 8001, 8002,
                    8007, 8008, 8009, 8010, 8011, 8021, 8022, 8031, 8042, 8045, 8080, 8081, 8082, 8083, 8084, 8085,
                    8086, 8087, 8088, 8089, 8090, 8093, 8099, 8100, 8180, 8181, 8192, 8193, 8194, 8200, 8222, 8254,
                    8290, 8291, 8292, 8300, 8333, 8383, 8400, 8402, 8443, 8500, 8600, 8649, 8651, 8652, 8654, 8701,
                    8800, 8873, 8888, 8899, 8994, 9000, 9001, 9002, 9003, 9009, 9010, 9011, 9040, 9050, 9071, 9080,
                    9081, 9090, 9091, 9099, 9100, 9101, 9102, 9103, 9110, 9111, 9200, 9207, 9220, 9290, 9415, 9418,
                    9485, 9500, 9502, 9503, 9535, 9575, 9593, 9594, 9595, 9618, 9666, 9876, 9877, 9878, 9898, 9900,
                    9917, 9929, 9943, 9944, 9968, 9998, 9999, 10000, 10001, 10002, 10003, 10004, 10009, 10010, 10012,
                    10024, 10025, 10082, 10180, 10215, 10243, 10566, 10616, 10617, 10621, 10626, 10628, 10629, 10778,
                    11110, 11111, 11967, 12000, 12174, 12265, 12345, 13456, 13722, 13782, 13783, 14000, 14238, 14441,
                    14442, 15000, 15002, 15003, 15004, 15660, 15742, 16000, 16001, 16012, 16016, 16018, 16080, 16113,
                    16992, 16993, 17877, 17988, 18040, 18101, 18988, 19101, 19283, 19315, 19350, 19780, 19801, 19842,
                    20000, 20005, 20031, 20221, 20222, 20828, 21571, 22939, 23502, 24444, 24800, 25734, 25735, 26214,
                    27000, 27352, 27353, 27355, 27356, 27715, 28201, 30000, 30718, 30951, 31038, 31337, 32768, 32769,
                    32770, 32771, 32772, 32773, 32774, 32775, 32776, 32777, 32778, 32779, 32780, 32781, 32782, 32783,
                    32784, 32785, 33354, 33899, 34573, 35500, 38292, 40193, 40911, 41511, 42510, 44176, 44442, 44443,
                    44501, 45100, 48080, 49152, 49153, 49154, 49155, 49156, 49157, 49158, 49159, 49160, 49161, 49163,
                    49165, 49167, 49175, 49176, 49400, 49999, 50000, 50001, 50002, 50003, 50006, 50300, 50389, 50500,
                    50636, 50800, 51103, 51493, 52673, 52822, 52848, 52869, 54045, 54328, 55055, 55056, 55555, 55600,
                    56737, 56738, 57294, 57797, 58080, 60020, 60443, 61532, 61900, 62078, 63331, 64623, 64680, 65000,
                    65129, 65389]

    if printOutput: print(B + "ATTACK INFORMATION:")
    if printOutput: print(B + "Target: " + W + ', '.join(domains))
    if printOutput: print(B + "Mode: " + W + mode)
    if args.top_web_ports:
        if printOutput: print(B + "Check ports: " + W + "top_web_ports")
    elif args.top_100_ports:
        if printOutput: print(B + "Check ports: " + W + "top_100_ports")
    elif args.top_1000_ports:
        if printOutput: print(B + "Check ports: " + W + "top_1000_ports")
    elif args.ports:
        if printOutput: print(B + "Check ports: " + W + str(ports))
    if printOutput: print(B + "Threads: " + W + str(threads))
    if printOutput: print(B + "Resolvers: " + W + ', '.join(res.nameservers))
    if printOutput: print(B + "Scan started: " + W + datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

    if printOutputV: print(Y + "\n[!] NOTE: Only new subdomains will be printed. No output from engine != no results.")

    # Check Python version
    if sys.version_info.major != 3:
        if printOutput: print(Y + "\n[!] You are using Python2. Python3 is recommended for better user experience")

    if mode.lower() == "passive":

        if printOutput: print(
            R + "\n[!] You selected passive mode. The subdomain will NOT be tested to ensure they are still available")

        runPassive(domains)

        if portsPassive:  # If we got ports from a passive engine...
            runOpenPortsPassive()

    elif mode.lower() == "active":


        # wl = open(WORDLIST_PATH, 'r')
        entries = WORDLIST_PATH.read_text().splitlines()
        entries = [line.strip() for line in entries if line]
        # x= len(entries)
        # x=1
        # wl.close()

        # Before starting the active scan, we test if the domain use wildcard,
        checkWildcard(domains)

        runActive(domains, entries, threads, args.no_bruteforce)

        # We run passive except if user expecify not to do it with --no-passive
        if args.no_passive:
            runPassive(domains)

        if args.top_web_ports:
            runOpenPorts(threads, topWebports)
        elif args.top_100_ports:
            runOpenPorts(threads, top100ports)
        elif args.top_1000_ports:
            runOpenPorts(threads, top1000ports)
        elif args.ports:
            ports = [int(i) for i in ports]  # Transform list of strings to list of ints
            runOpenPorts(threads, ports)
        else:
            if printOutput: print(R + "\n[-] No ports provided so scan will not be made.")

    else:
        if printOutput: print(
            R + "\n[-] No mode selected. Mode available: active, passive\n\n[!] Example: python Dome.py -m passive -d domain.com")
        exit()

    if outputFlag:
        mode_info = mode.lower()
        output(output_file, mode_info)

    if printOutput: print("\n" + Y + json.dumps(subdomains_found, sort_keys=False, indent=4))
    if printOutput: print(W + "\n[+] " + str(len(subdomains_found_list)) + B + " unique subdomains found\n")
    if printOutput: print("[+] Program finished at " + datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
