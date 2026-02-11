import re
from datetime import datetime

from datetime import timezone
import dateutil

import bs4

import pprint

from civic_scraper.base.constants import SUPPORTED_ASSET_TYPES


class ParsingError(Exception):
    pass


class Parser:
    def __init__(self, html):
        self.html = html
        self.soup = bs4.BeautifulSoup(html, "html.parser")
#        print(self.soup.prettify())

    def parse(self):
        #MunicodeMeetings doesn't use divs, it splits by table row
#        divs = self._get_divs_by_board()
        rows = self._get_trs_by_board()

#        print("Rows:")
#        pprint.pprint(rows)
        metadata = self._extract_asset_data(rows)
        return metadata

    def _get_trs_by_board(self):
#        return self.soup.find_all("tr", id=re.compile(r"(even|odd)"))
        return self.soup.find_all("tr")

    #Unused
    def _get_divs_by_board(self):
        "Locate top-level divs containing meeting details for each board or entity"
        return self.soup.find_all("div", id=re.compile(r"cat\d+"))

    def _extract_asset_data(self, divs):
        "Extract asset-level data from each board/entity div"

        #### Divs is actually 'trs', I just can't be fucked to fix it

        # bs4 helper
        def file_links_with_no_title(tag):
            # HTML link appears in meeting title and download menu.
            # This filters out the initial link

            # Patrick - Unfortunately each of the tr/td entries is filled with some redundant data
            # PDF Agenda
            # HTML Agenda
            # PDF Agenda
            # HTML Agenda
            # Addendum pdf (Supplimental)
            # Possible additional Addendum
            # PDF Minutes (Usually a link to the PDF Agenda)
            # Video link /bc-*
            return (
                tag.name == "a"
                and tag.get("href", "").endswith(".pdf")
#.startswith("/AgendaCenter/ViewFile")
#                and not tag.has_attr("title")
            )

        metadata = []
        # Links often appear twice (once under meeting title, once in download menu)
        # so we track which we've already seen to avoid duplicate entries
        bookkeeping = set()
        #Skip the first row
        for div in divs[1:]:
#            print("Reading row:")
#            pprint.pprint(div)
            cmte_name = self._committee_name(div)

            #Skip cancelled meetings
            if "CANCELLED" in cmte_name:
                continue

            #I don't like this but it's how they did it.
            meeting_title = cmte_name
            #I don't see a distinct meeting id classification, we can possibly parse the fileattachments entry
            meeting_id = self._mtg_id(div)
            if not meeting_id:
                meeting_id = meeting_title

            #OK OK OK Date tiem
            meeting_date = self._mtg_date(div)

            #URL Tiem
            files = self._mtg_files(div)

            for file in files:
                metadata.append(
                    {
                        "url_path":file,
                        "committee_name":cmte_name,
                        "meeting_title":meeting_title,
                        "meeting_id":meeting_id,
                        "meeting_date":meeting_date,
                        "meeting_time":None, #Dis in date
                        "asset_type":"pdf",
                    }
                )
                bookkeeping.add(file)




            # Line-item data for each meeting is inside table rows. Typically one row, but possibly multiple if several meetings listed within the 
            # time span for a given govt entity

            #This is wrong

#            for row in div.tbody.find_all("tr"):
#                meeting_title = self._mtg_title(row)
#                meeting_id = self._mtg_id(row)
#                links = row.find_all(file_links_with_no_title)
#                # Each meeting has multiple asset types
#                for link in links:
#                    # Skip links to page listing previous agenda versions
#                    if self._previous_version_link(link):
#                        continue
#                    # Skip previously harvested links
#                    if link["href"] in bookkeeping:
#                        continue
#                    metadata.append(
#                        {
#                            "committee_name": cmte_name,
#                            "url_path": link["href"],
#                            "meeting_date": self._mtg_date(row),
#                            "meeting_time": None,
#                            "meeting_title": meeting_title,
#                            "meeting_id": meeting_id,
#                            "asset_type": self._asset_type(link["href"]),
#                        }
#                    )
#                    bookkeeping.add(link["href"])
        return metadata
    def _mtg_files(self,row):
        cols = row.find_all('td')
        outFiles = []
        for col in cols:
            for hreft in col.find_all('a'):
                if hreft.get("href", "").endswith(".pdf"):
                    if hreft.get("href", "") not in outFiles:
                        outFiles.append(hreft.get("href",""))
#                and tag.get("href", "").endswith(".pdf")
        return outFiles

    def _committee_name(self, row):
        # If present, remove span that contains
        # arrow ▼ for toggling meeting list
        #
        # Patrick - committee name is actually the second td
        cols = row.find_all('td')

#        print("Columns found:")
#        pprint.pprint(cols)

        try:
            output = cols[1].extract().text
        except:
            output = cols[1].text

#        try:
#            div.h2.span.extract()
#        except AttributeError:
#            pass
#        header_node = div.h2 or div.h3
#        return header_node.text.strip()
        print("Pushing out committee name: %s" % str(output.strip()) )
        return output.strip()

    #Unused
    def _mtg_title(self, row):
        return row.p.text.strip()

    def _mtg_date(self, row):
        cols = row.find_all('td')

        mdate = cols[0].span.get('content')
        print("mtg_date acquired: %s" % str(dateutil.parser.parse(mdate)) )
        return dateutil.parser.parse(mdate)
#        return datetime.strptime(mdate, "%Y-%m-%dT%H:%M:%S")

#        month, day, year = re.match(r"_(\d{2})(\d{2})(\d{4}).+", row.a["name"]).groups()
#        return datetime(int(year), int(month), int(day))

    #Meeting id
    def _mtg_id(self, row):
        cols = row.find_all('td')
        #The fifth column has the closest thing to a meeting id.
        for hreft in cols[5].find_all('a'):
            #hreft.href.extract()
            if 'fileattachments' in hreft.get("href", ""):
                #Break out when we get a match
                return re.match(r"/meeting/([0-9]+)/").group(1)
        #Otherwise return none we'll call it the same shit
        return None
#        return row.a["name"]

    def _asset_type(self, url_path):
        if url_path.endswith("packet=true"):
            return "agenda_packet"
        asset_type = url_path.split("/")[3].lower()
        if asset_type in SUPPORTED_ASSET_TYPES:
            return asset_type
        else:
            msg = f"Unexpected asset type ({asset_type}) for {url_path}"
            raise ParsingError(msg)

    def _previous_version_link(self, link):
        return "PreviousVersions" in link["href"]
