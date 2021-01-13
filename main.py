import json
import random
import re
import smtplib
from email.message import EmailMessage
from time import sleep

import numpy as np
import requests
from bs4 import BeautifulSoup

from __old__ import *

# dicts
NUMBERS_DICT = {1: "one", 2: "two", 3: "three", 4: "four"}

# !!!
# TUTAJ DAJ SWOJE PREFERENCJE
# !!!
MIASTO = "warszawa"
MIN_KWOTA = 900
MAKS_KWOTA = 2200
POKOJE = [2]

PRZEKLETE_DZIELNICE = ["bemow", "rembertów", "nowodwor", "białołęka", "bialoleka", "gocław", "bródn", "wawer", "wesoła",
                       "wilanów", "ursus"]
# PRZEKLETE_DZIELNICE = stare_klatwy
PRZEKLETE_SLOWA = PRZEKLETE_DZIELNICE
PRZEKLETE_PATTERNY = [r"bez zwierz[aą]t"] + stare_patterny

# zaladuj dane teleadres
try:
    with open("config.json") as file:
        data = json.loads(file.read())
        HOST_EMAIL = data["host_email"]
        RECIPIENTE = data["recipients"]
        HOST_PASSWORD = data["password"]
    CONFIG_FILE_READ = True


except FileNotFoundError as ex:
    CONFIG_FILE_READ = False
    # LOGOSWANIE DO MAILA:
    HOST_EMAIL = input("Podaj prosze swój email...")
    HOST_PASSWORD = input("Daj prosze swoje haslo do maila " + HOST_EMAIL + "......: ")
    RECIPIENTE = input("Daj prosze maile odbiorcow... separowane spacjami... ").split(" ")
    print(".\n" * 100)

# INNE GLOBALE
LINKS_FILENAME = "links.csv"
INTER_HACK_TIME = 60 * 90  # in seconds


class CursedLinkException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


def levenshtein(seq1, seq2):
    size_x = len(seq1) + 1
    size_y = len(seq2) + 1
    matrix = np.zeros((size_x, size_y))
    for x in range(size_x):
        matrix[x, 0] = x
    for y in range(size_y):
        matrix[0, y] = y

    for x in range(1, size_x):
        for y in range(1, size_y):
            if seq1[x - 1] == seq2[y - 1]:
                matrix[x, y] = min(
                    matrix[x - 1, y] + 1,
                    matrix[x - 1, y - 1],
                    matrix[x, y - 1] + 1
                )
            else:
                matrix[x, y] = min(
                    matrix[x - 1, y] + 1,
                    matrix[x - 1, y - 1] + 2,
                    matrix[x, y - 1] + 1
                )
    # print (matrix)
    return matrix[size_x - 1, size_y - 1]


def PRINT(thing):
    """
    wypisuje tekst tylko ze GŁOSNO
    """
    print(str(thing).upper())


class LinkChecker:
    def __init__(self, link: str):
        self.link = link

    def district_check_oldschool(self):
        """
        deprecated but still used for gumtree
        """
        for dzielnica in PRZEKLETE_DZIELNICE:
            if dzielnica in self.link:
                raise CursedLinkException("znalazlem przekleta dzielnice: " + dzielnica)

    def district_check_newschool(self):
        """
        nice and newschool. uses levenshtein distance!
        """

        # splituje link na słowa:
        slowa = self.link.split('-')
        for slowo in slowa:
            for dzielnica in PRZEKLETE_DZIELNICE:
                dystans = levenshtein(dzielnica, slowo)
                if dystans <= 2:
                    raise CursedLinkException(
                        "znalazlem przekleta dzielnice: " + dzielnica + " odleglosc od niej to " + str(dystans))

    def district_check(self):
        if "gumtree" in self.link:
            self.district_check_oldschool()
        self.district_check_newschool()

    def content_check(self):
        # SPRAWDZMY CZY MOZE JEST NA TEJ STRONIE PRZEKLETE SLOWO

        html = requests.get(self.link).text
        if "gumtree" in self.link:
            soup = BeautifulSoup(html, features="html.parser")
            html = str(soup.find("div", {"class": "description"}))
        elif "olx" in self.link:
            soup = BeautifulSoup(html, features="html.parser")
            html = str(soup.find("div", {"id": "textContent"}))
        elif "otodom" in self.link:
            pass  # TODO nie wiem jak wyciągnac wlasciwy content

        for slowo in PRZEKLETE_SLOWA:
            if slowo in html.lower() or slowo in self.link:
                raise CursedLinkException("ZNALAZLEM PRZEKLETE SLOWO: " + slowo)

        for pat_i, pattern in enumerate(PRZEKLETE_PATTERNY):
            regex_match = re.search(pattern, html.lower())
            if regex_match:
                raise CursedLinkException("znalazlem przeklety pattern: " + str(pat_i) + ": " + regex_match.group())

    def check_link(self) -> bool:
        print(".")
        print("weryfikuje link: " + self.link)

        try:
            self.district_check()
            self.content_check()
        except CursedLinkException as ex:
            PRINT(ex)
            return False
        else:
            print("ten link jest spoko")
            return True


def verify_gozo(nowalista):
    templist = []
    for link in nowalista:
        lc = LinkChecker(link)
        if lc.check_link():
            templist.append(link)
    nowalista = templist
    return nowalista


def scrape_olx():
    print("\nROZPOCZYNAM hakowanie OLXa")
    print(".")

    url = f"https://www.olx.pl/nieruchomosci/mieszkania/wynajem/{MIASTO}/?search[filter_float_price%3Afrom]={MIN_KWOTA}&search[filter_float_price%3Ato]={MAKS_KWOTA}&search[private_business]=private"
    for i, op in enumerate(POKOJE):
        if op <= 4:
            url += f"&search[filter_enum_rooms][{i}]={NUMBERS_DICT[op]}"
    url += "&search[photos]=1"

    soup = BeautifulSoup(requests.get(url).text, features="html.parser")
    offers = soup.find("table", {"id": "offers_table"})
    if offers is None:
        print("DZIWNY ERROR: ")
        print(soup)
        raise e
    else:
        rows = offers.find_all("tr")

    found_links = []

    for i in range(len(rows) - 1):
        row = rows[i + 1]
        a = row.a
        if a is not None:
            newlink = a.get("href")
            if newlink is not None and newlink != "#":
                found_links.append(newlink)

    # HACKERMAN
    return [link for li, link in enumerate(found_links) if li % 2 == 0]


def scrape_gumtree():
    print("\nROZPOCZYNAM hakowanie GUMNTRAa")
    print(".")

    urlist = []
    found_links = []

    for op in POKOJE:
        urlist.append(
            f"https://www.gumtree.pl/s-mieszkania-i-domy-do-wynajecia/{MIASTO}/v1c9008l3200008p1?nr={op}&pr={MAKS_KWOTA},{MIN_KWOTA}")

    for url in urlist:
        soup = BeautifulSoup(requests.get(url).text, features="html.parser")
        offers = soup.find_all("div", {"class": "result-link"})

        for offer in offers:
            a = offer.a
            if a is not None:
                newlink = "https://www.gumtree.pl" + a.get("href")  # UWAGA JESTEM HAKEREM
                if newlink is not None and newlink != "#":
                    found_links.append(newlink)

    return found_links


def load_old_links(filename):
    file = open(filename, "r+")
    rows = file.read().split('\n')
    file.close()
    links = []
    for row in rows:
        if len(row.split('|')) > 1:
            links.append(row.split('|')[1])
    return links


def load_counter(filename):
    file = open(filename, "r+")
    rows = file.read().split('\n')
    file.close()
    last_row = rows[len(rows) - 2].split('|')
    return int(last_row[0])


def voynich_generator(seed: int) -> str:
    """
    always good to have one.
    :return: a slovo
    """
    prefixy = ["xi", "be", "su", "ta", "ro", "pu", "lo", "fero", "pi", "ju", "je", "ja"]
    intefixy = ["de", "ra", "ko", "su", "ke", "for", "kus", "rami", "n", "non", "suko"]
    sufixy = ["za", "fi", "no", "tix", "ter", "mer", "pir", "sena", "soto", "zur", "dos", "dex", "dek", "le", "ra"]
    random.seed(seed)
    bub = random.random()
    if bub <= 0.3333333333333:
        slowo = random.choice(prefixy) + random.choice(intefixy) + random.choice(sufixy)
    elif bub <= 0.6666666666666:
        slowo = random.choice(prefixy) + random.choice(sufixy)
    else:
        slowo = random.choice(prefixy) + random.choice(intefixy) + random.choice(intefixy)
    return slowo


def log(err):
    # file i/o
    pass


if __name__ == '__main__':

    # załaduj poprzednio znalezione linki se
    old_links = load_old_links(LINKS_FILENAME)

    offer_counter = load_counter(LINKS_FILENAME)

    work = True

    while work:

        found_links = []
        try:
            found_links += (scrape_olx())
            found_links += (scrape_gumtree())

        except requests.exceptions.ConnectionError as err:
            print("COS JEST NIE TAK Z KOMINTERNETEM moze burza uderzyla w twoj router")
            print("SPRÓBUJE ZNOWU ZA 10 MINUT MAM NADZIEJE ZE ZRESETUJESZ ROUTER")
            log(err)
            sleep(600)
        except requests.exceptions.Timeout:
            print("timeout serwera, ide spać na minute i prubuje znowu")
            sleep(60)
            print("ok próbuje znowu")
        except requests.exceptions.TooManyRedirects:
            print("ERROR:::: NIE WIEM CO SIE TU STAŁO")
        except requests.exceptions.HTTPError as err:
            PRINT("O KURWA STARY: " + str(err))
        except requests.exceptions.RequestException as e:
            print("KATASTROFICZNY ERROR. ABORTUJEMY OPERACJE")
            work = False

        else:
            print(".")
            print(".")

            # znajdzmy se nowe linki tzn tych ktorych nie mialem wczesniej w pliku
            nowalista = [link for link in found_links if link not in old_links]
            print("Znalazlem " + str(len(nowalista)) + " nowych linkow...")

            # ZWERYFIKUJ OSTATECZNIE LINKI
            if len(nowalista) > 0:
                PRINT("WERYFIKUJE LINKI")
                nowalista = verify_gozo(nowalista)

            temp = offer_counter
            content = ""

            # zbuduj content, wypisz linki:
            if len(nowalista) > 0:
                print("\nOTO SĄ SPOKO LINKI:")

                for link in nowalista:
                    offer_counter += 1
                    funnyname = voynich_generator(offer_counter)
                    print("#" + funnyname + " ::: " + link)
                    content += "#" + funnyname + ":: " + link + "\n\n"
            else:
                print("\nnima nic nowego fajnego")

            # wysylanie maila:
            if len(nowalista) > 0:
                PRINT("PROBUJE WYSLAC MAILA......... ")

                msg = EmailMessage()
                msg["From"] = HOST_EMAIL
                msg['To'] = ", ".join(RECIPIENTE)
                msg["Subject"] = "swieze info z olx :)"
                msg.set_content(content)

                smtp_server = smtplib.SMTP('smtp.gmail.com', port=587)
                smtp_server.ehlo()
                smtp_server.starttls()
                smtp_server.login(HOST_EMAIL, HOST_PASSWORD)

                smtp_server.send_message(msg)
                print("wyslalem maila ;)")

                # zapisz wyslane linki do links.csv
                file = open(LINKS_FILENAME, "a")
                for link in nowalista:
                    old_links.append(link)
                    temp += 1
                    file.write(str(temp) + '|' + link + '\n')
                file.close()

            else:
                print("nie wyslalem maila, siema")

            # koniec
            print("KONIEC IDE SPAC NA " + str(INTER_HACK_TIME / 60) + " MINUT")
            for i in range(int(INTER_HACK_TIME / 60)):
                sleep(60)
                print(str(i + 1))
