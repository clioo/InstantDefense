from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from imap_tools import MailBox, Q
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
from contextlib import closing
from tika import parser
import shutil
import urllib.request as request
import os
import re
import imaplib, email
import json
import time
import sys
import time
import csv
import datetime
import re
import requests


PROXY = { 'https' : 'https://instantdefense-country-US:6ee10e-6854eb-107264-6e0f88-b9c453@premium.residential.proxyrack.net:10000'} 


class InstantDefense:

    def __init__(self, debug=False, proxy=False):
        self.web_pages = {
            'ocsd': 'http://ws.ocsd.org/ArrestLog/ArrestLogMain.aspx',
            'hcdistrictclerk': 'https://www.hcdistrictclerk.com/edocs/public/search.aspx?newsuits=1',
            'outlook': 'https://outlook.live.com/mail/0/',
            'dallascounty': 'https://www.dallascounty.org/jaillookup/search.jsp',
            'sbcounty': 'http://web.sbcounty.gov/sheriff/bookingsearch/bookingsearch.aspx',
            'tylerpaw': 'http://tylerpaw.co.fort-bend.tx.us/PublicAccess/default.aspx',
            'azbar': 'https://azbar.legalserviceslink.com/lawyers/search/advanced',
            'floridabar': 'https://www.floridabar.org/directories/find-mbr/?lName=&sdx=N&fName=&eligible=Y&deceased=N&firm=&locValue=Miami+dade&locType=T&pracAreas=C16&lawSchool=&services=&langs=&certValue=&pageNumber=1&pageSize=50',
            'osceola': 'https://apps.osceola.org/Apps/CorrectionsReports/Report/Daily/',
            'seminoleclerk': 'https://courtrecords.seminoleclerk.org/criminal/default.aspx',
            'ocfl': 'https://apps.ocfl.net/bailbond/',
        }
        options = webdriver.ChromeOptions()
        options_wire = {
                'proxy': {
                'http': 'http://instantdefense-country-US:6ee10e-6854eb-107264-6e0f88-b9c453@premium.residential.proxyrack.net:10000', 
                'https': 'https://instantdefense-country-US:6ee10e-6854eb-107264-6e0f88-b9c453@premium.residential.proxyrack.net:10000', 
                'no_proxy': 'localhost,127.0.0.1' # excludes
            }
        }
        if debug:
            # This will open the browser, just for debugging
            # purposes
            if proxy:
                self.driver = webdriver.Chrome(seleniumwire_options=options_wire)
            else:
                self.driver = webdriver.Chrome()
            self.driver.maximize_window()
        else:
            # Open the browser in the background, this is used
            # in servers that have no GUI
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920x1080')
            if proxy:
                self.driver = webdriver.Chrome(options=options, seleniumwire_options=options_wire)
            else:
                self.driver = webdriver.Chrome(options=options)
 

    # Private methods
    def _export_to_csv(self, data, file_name):
        """Data must be an array of dictionaries so it can export it"""
        if data:
            keys = data[0].keys()
            with open(f'./results/{file_name}_results.csv', 'w') as output_file:
                dict_writer = csv.DictWriter(
                    output_file,
                    fieldnames=keys,
                    lineterminator='\n'
                )
                dict_writer.writeheader()
                dict_writer.writerows(data)

    def _read_config_file(self, key, default=''):
        """Read data from json config file,
        if doesn't find it, returns a default value"""
        data = default
        with open('config.json') as config_file:
            jsonConfig = json.load(config_file)
            data = jsonConfig.get(key, default)
        return data

    def _write_config_file(self, key, value):
        """Gets the json config file, modify a value and close it"""
        with open('config.json', 'r+') as config_file:
            data = json.load(config_file)
            data[key] = value
            config_file.seek(0)
            json.dump(data, config_file)
            config_file.truncate()

    def _get_last_imap_emails(self):
        """Gets the last emails from inbox"""
        email = self._read_config_file('email')
        password = self._read_config_file('password')
        imap_url = self._read_config_file('imap_url')
        with MailBox(imap_url).login(email, password, 'INBOX') as mailbox:
            mails = [msg for msg in mailbox.fetch(Q(all=True))]
            latest_email = mails[-1]
        return latest_email.html

    def _wait_until(self, query, by=By.CSS_SELECTOR, until=EC.element_to_be_clickable, wait_time=30):
        """generic wait until class with default csss selector and
        element to be clickable"""
        element = WebDriverWait(self.driver, wait_time).until(
            until((by, query))
        )
        return element

    def _dallascounty_is_query_found(self, query_input_locator, bkin_number,
                                     wrong_message_locator, search_button_locator,
                                     name_link_locator):
        """This method returns true if query was found, it is always executed
        at the main page"""
        is_found = False

        # Now we handle whether bookin number was found or not
        try:
            query_input = self._wait_until(query_input_locator)
            search_button = self._wait_until(search_button_locator)
            query_input.send_keys(bkin_number)
            search_button.click()
            # This could be a wrong message or the name of the found bookin
            next_element = self._wait_until(
                f"{wrong_message_locator}, {name_link_locator}"
            )
            if next_element.tag_name == 'a':
                is_found = True
        except:
            is_found = False
        return is_found

    def _ocsd_submit(self):
        email = self._read_config_file('email')
        # Submit the form and read the sent email
        submit_button_selector = '#btnSearch'
        email_input_selector = '#txtEmail'
        invalid_email_selector = '#lblMessage'
        # Submit the form
        self.driver.get(self.web_pages['ocsd'])
        submit_button = self._wait_until(submit_button_selector)
        submit_button.click()
        email_input = self._wait_until(email_input_selector)
        email_input.send_keys(email)
        submit_button = self._wait_until(submit_button_selector)
        submit_button.click()
        self._wait_until(invalid_email_selector)

    def _bs4_get_data_from_table(self, soup):
        """This method only works for beautiful soup 4 and parses a html table
        to an list of dictionaries"""
        rows = soup.select('tr')
        headers = rows[0].select('th')
        rows = rows[1:]
        data = []
        for row in rows:
            cells = row.select('td')
            data_item = {}
            for i, cell in enumerate(cells):
                key = headers[i].get_text()
                data_item[key] = cell.get_text()
            data.append(data_item)
        return data

    def _read_last_email(self):
        """This method returns the last email body you get in the email account"""
        email = self._read_config_file('email')
        password = self._read_config_file('password')
        # Locators
        log_in_link_selector = 'nav.auxiliary-actions > ul a.sign-in-link, div.c-group.links :nth-child(2) > a'
        email_input_selector = 'input[type=email]'
        password_input_selector = 'input[type=password]'
        next_button_selector = 'input[type=submit]'
        sign_in_button_selector = 'input[type=submit]'
        mails_selector = 'div[role=option]'
        body_mail_selector = 'div.wide-content-host > div > div + div > div table'
        # Let's read the last mail mail !
        self.driver.get(self.web_pages['outlook'])
        log_in_link = self._wait_until(log_in_link_selector)
        log_in_link.click()
        tabs = self.driver.window_handles
        if len(tabs) > 1:
            self.driver.switch_to.window(tabs[1])
        email_input = self._wait_until(email_input_selector)
        email_input.send_keys(email)
        next_button = self._wait_until(next_button_selector)
        next_button.click()
        password_input = self._wait_until(password_input_selector)
        password_input.send_keys(password)
        sign_in_button = self._wait_until(sign_in_button_selector)
        sign_in_button.click()
        mail = self._wait_until(mails_selector)
        mail.click()
        body_mail = self._wait_until(body_mail_selector)
        # reading rows
        rows = body_mail.find_elements(By.TAG_NAME, 'tr')
        keys = rows[0].find_elements(By.TAG_NAME, 'th')
        # Removing header row
        rows = rows[1:]
        data = []
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, 'td')
            data_item = {}
            for i, cell in enumerate(cells):
                data_item[keys[i].text] = cell.text
            data.append(data_item)
        self._export_to_csv(data, 'OCSDemail')
        return data

    def _tylerpaw_get_case_details(self):
        """Gets the case details"""
        # locators
        name_locator = 'th#PIr11'
        address_locator = "(//td[contains(@headers, 'PIr01') and contains(@headers, 'PIr11')])[3]"
        attorneys_locator = "(//td[contains(@headers, 'PIr01') and contains(@headers, 'PIr11')])[2]/b"
        crime_info_locator = "//*[contains(text(), 'Charges')]/ancestor::table//tr[2]/td[2]"
        has_arraignment_locator = "//*[contains(text(), 'Arraignment')]"
        # scrape
        data = {}
        name = self._wait_until(name_locator)
        address = self._wait_until(address_locator, by=By.XPATH)
        try:
            attorneys = self._wait_until(attorneys_locator, by=By.XPATH, wait_time=0.5)
        except:
            attorneys = False
        crime_info = self._wait_until(crime_info_locator, by=By.XPATH)
        try:
            has_arraignment =  self._wait_until(
                has_arraignment_locator,
                by=By.XPATH,
                wait_time=0.5
            )
        except:
            has_arraignment = False
        data['name'] = name.text
        data['address'] = address.text
        data['attorneys'] = attorneys.text if attorneys else "No Attorneys"
        data['crime_info'] = crime_info.text
        data['has_arraignment'] = True if has_arraignment else False
        self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[0])
        return data

    def _open_link_new_tab(self, link):
        """Opens a new tab and navigates to the given link"""
        self.driver.execute_script("window.open('');")
        self.driver.switch_to.window(self.driver.window_handles[1])
        self.driver.get(link)

    def _azbar_contact_info(self, link):
        #Locators
        contact_information_locator = "div.jobAppDetailBT div.hlfWidtleft:nth-child(1) p"
        name_locator = "div.applicantDtl > h3"
        info = {
            'name': '',
            'phone_number': '',
            'email': '',
            'web_page': '',
            'address': ''
        }
        # Regular expressions
        phone_number_regex = r'^[+]*[(]{0,1}[0-9]{1,4}[)]{0,1}[-\s\./0-9]*$'
        address_regex = r'^(\d+) ?([A-Za-z](?= ))? (.*?) ([^ ]+?) ?((?<= )APT)? ?((?<= )\d*)?$'
        # Request
        with requests.Session() as session:
                page = requests.get(link)
                soup = BeautifulSoup(page.content)
                name_element = soup.select_one(name_locator)
                name = name_element.getText()
                contact_info_element = soup.select_one(contact_information_locator)
                contact_info = contact_info_element.getText()
                contact_info = contact_info.replace('\t', '')
                splitted_info = contact_info.split('\n')
                info['name'] = name.strip()
                for single_info in splitted_info:
                    single_info = single_info.strip()
                    if 'http' in single_info:
                        info['web_page'] = single_info
                    elif re.search(phone_number_regex, single_info):
                        info['phone_number'] = single_info
                    elif '@' in single_info:
                        info['email'] = single_info
                    elif re.search(address_regex, single_info):
                        info['address'] = single_info
        return info
    
    def _clean_string(self, cad, replace=''):
        cad = cad.strip()
        cad = cad.replace('\t', replace)
        cad = cad.replace('\n', replace)
        cad = cad.replace(':', replace)
        cad = cad.replace('\xa0', replace)
        return cad
    
    def _floridabar_single_info(self, link):
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'en,en-US;q=0.9,es-419;q=0.8,es;q=0.7,es-ES;q=0.6,en-GB;q=0.5',
            'cache-control': 'max-age=0',
            'cookie': '__cfduid=d8cda280e8ca10be7cb18ffcbc024fd1d1598332470; PHPSESSID=j1sosdptg77ahcrs8pors730jcht9phm; _gcl_au=1.1.2001199616.1598354074; _ga=GA1.2.765898054.1598354074; _gid=GA1.2.790579873.1598354074; _fbp=fb.1.1598354074442.946758036; cf_clearance=ecf667dc23b7bd5fe37b4aea1e0a2d87fb5846a3-1598335991-0-1z759cc670z6c56a614z86e63aa-150; _dc_gtm_UA-50390294-1=1',
            'referer': 'https://www.floridabar.org/directories/find-mbr/?lName=&sdx=N&fName=&eligible=Y&deceased=N&firm=&locValue=Miami+dade&locType=T&pracAreas=C16&lawSchool=&services=&langs=&certValue=&pageNumber=1&pageSize=50',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.135 Safari/537.36 Edg/84.0.522.63'
        }
        # Locators
        name_locator = 'h1.full'
        row_keys_data_locator = 'div#mProfile div.row > div:nth-child(1)'
        row_values_data_locator = 'div#mProfile div.row > div:nth-child(2)'
        # Search
        info = {
            'Name': '',
            'Bar Number': '',
            'Mail Address': '',
            'Physical Address': '',
            'Email': '',
            'Personal Bar URL': '',
            'County': '',
            'Circuit': '',
            'Admitted': '',
            'Law School': '',
            'Sections': '',
            'Practice Areas': '',
            'Federal Courts': '',
            'Firm': '',
            'Firm Size': '',
            'Firm Position': '',
        }
        with requests.Session() as session:
            page = session.get(link, headers=headers)
            soup = BeautifulSoup(page.content)
            rows_keys = soup.select(row_keys_data_locator)
            rows_values = soup.select(row_values_data_locator)
            try:
                info['Name'] = self._clean_string(soup.select_one(name_locator).get_text())
                for key, value in zip(rows_keys, rows_values):
                    key = self._clean_string(key.get_text())
                    cleaned_value = self._clean_string(value.get_text())
                    if key in info.keys():
                        info[key] = cleaned_value
                        if key == 'Email':
                            email = self._clean_string(
                                soup.select_one('a.icon-email').get_text()
                            )
                            info['Email'] = email
                        elif key == 'Mail Address' or key == 'Physical Address':
                            info[key] = self._clean_string(value.get_text(), '|')
                return info
            except Exception as e:
                return

    def _floridabar_single_info_selenium(self, link):
        # Locators
        name_locator = 'h1.full'
        row_keys_data_locator = 'div#mProfile div.row > div:nth-child(1)'
        row_values_data_locator = 'div#mProfile div.row > div:nth-child(2)'
        self.driver.get(link)
        info = {
            'Name': '',
            'Bar Number': '',
            'Mail Address': '',
            'Physical Address': '',
            'Email': '',
            'Personal Bar URL': '',
            'County': '',
            'Circuit': '',
            'Admitted': '',
            'Law School': '',
            'Sections': '',
            'Practice Areas': '',
            'Federal Courts': '',
            'Firm': '',
            'Firm Size': '',
            'Firm Position': '',
        }
        rows_keys = self.driver.find_elements_by_css_selector(row_keys_data_locator)
        rows_values = self.driver.find_elements_by_css_selector(row_values_data_locator)
        try:
            info['Name'] = self._clean_string(self.driver.find_element_by_css_selector(name_locator).text)
            for key, value in zip(rows_keys, rows_values):
                key = self._clean_string(key.text)
                cleaned_value = self._clean_string(value.text)
                if key in info.keys():
                    info[key] = cleaned_value
                    if key == 'Email':
                        email = self._clean_string(
                            self.driver.find_element_by_css_selector('a.icon-email').text
                        )
                        info['Email'] = email
                    elif key == 'Mail Address' or key == 'Physical Address':
                        info[key] = self._clean_string(value.text, '|')
            return info
        except Exception as e:
            self.driver.get(self.web_pages['floridabar'])
            print("Detected as attack, retrying after waiting 20 seconds")
            time.sleep(20)
            info = self._floridabar_single_info(link)
            return info
        
    def _seminoleclerk_get_extradata(self, link, headers, cookies):
        address_locator = 'span#lbl_Contact > table tr td:nth-child(2)'
        party_btn_locator = '#party_pan'
        has_attrny_locator = '#lbl_attyDetails'
        with requests.session() as conn:
            extradata = {}
            for cookie in cookies:
                conn.cookies.set(cookie.get('name'), cookie.get('value'))
            response = conn.get(link, headers=headers)
            soup = BeautifulSoup(response.content)
            addresses = soup.select(address_locator)
            addresses = [self._clean_string(addr.get_text(), ' ') for addr in addresses]
            has_attrny = soup.select_one(has_attrny_locator)
            try:
                extradata['address'] = ' '.join(addresses)
                has_attrny = has_attrny.select('tr')
                has_attrny = has_attrny[1].select('td')
                has_attrny = has_attrny[1]
                extradata['has_attrny'] = has_attrny.get_text()
            except:
                pass
            return extradata

    # Public methods
    def ocsd_submit_read_mail(self):
        """Submits OCSD form and read data from a IMAP account"""
        self._ocsd_submit()
        print('Reading email...')
        email_body = self._get_last_imap_emails()
        soup = BeautifulSoup(email_body)
        data = self._bs4_get_data_from_table(soup)
        self._export_to_csv(data, 'OCSD')
        return data

    def hcdistrictclerk_login(self):
        """Just a login method"""
        hcdistrictclerk_email = self._read_config_file('hcdistrictclerk_email')
        hcdistrictclerk_password = self._read_config_file(
            'hcdistrictclerk_password'
        )
        self.driver.get(self.web_pages['hcdistrictclerk'])
        # Locators
        form_frame_locator = '#ctl00_ctl00_ctl00_TopLoginIFrame1_iFrameContent2'
        email_input_selector = '#txtUserName'
        password_input_selector = '#txtPassword'
        login_button_selector = '#btnLoginImageButton'
        # Login steps
        self.driver.switch_to.frame(self._wait_until(form_frame_locator))
        email_input = self._wait_until(email_input_selector)
        password_input = self._wait_until(password_input_selector)
        login_button = self._wait_until(login_button_selector)
        email_input.send_keys(hcdistrictclerk_email)
        password_input.send_keys(hcdistrictclerk_password)
        login_button.click()

    def dallascounty_bookin_search(self):
        """Using a for loop to do the bookin search.
        Output format (list of dictionaries):
            - [{'name': 'Name 1', 'birth_date': '1969-07-20'}]"""
        self.driver.get(self.web_pages['dallascounty'])
        dict_data = {
            'Race': '', 'Sex': '', 'Jail Location': '',
            'Tank Location': '', 'Bookin Number': '',
            'Bookin Date': '', 'Bond Amount': '',
            'Charge': '', 'Warrant Number': '', 'Magistrate': '',
            'Remark': '',
        }
        allowed_heades = set(dict_data.keys())
        # Locators
        bkin_num_input_locator = 'input[name=bookinNumber]'
        search_button_locator = 'form[name=searchByBookin] input[type=submit]'
        wrong_message_locator = 'div.alert-danger'
        new_search_button_locator = "//a[contains(text(), 'New Jail Lookup')]"
        name_link_locator = 'a.btn-primary'
        birth_date_locator = 'table.table > tbody > tr :nth-child(4)'
        person_link_locator = 'table.table a.btn'
        headers_locator = "td[align='right']"
        values_locator = "td[align='left']"
        # We start searching
        bkin_num_input = self._wait_until(bkin_num_input_locator)
        search_button = self._wait_until(search_button_locator)
        output_names_birth_dates = []
        init_bookin_number = int(self._read_config_file('last_bookin_success',
                                                        '20018914'))
        last_bookin_success = int(init_bookin_number)
        for i in range(0, 400):
            single_data = dict_data.copy()
            time.sleep(0.5)
            bkin_number = init_bookin_number + i
            print(bkin_number)
            if bkin_number == 20031557:
                import pdb; pdb.set_trace()
            # We search for the person by bookin_number value
            is_found =  self._dallascounty_is_query_found(
                bkin_num_input_locator,
                str(bkin_number),
                wrong_message_locator,
                search_button_locator,
                name_link_locator
            )
            # If it's found, we store it and click on New Search button
            if is_found:
                last_bookin_success = str(bkin_number)
                # Now we store names and birth date in a list
                name = self._wait_until(name_link_locator).text
                birth_date = self._wait_until(birth_date_locator).text
                time.sleep(0.3)
                person_link = self._wait_until(person_link_locator).click()
                single_data['Name'] = name
                single_data['Birth date'] = birth_date
                self._wait_until(headers_locator)
                headers = self.driver.find_elements_by_css_selector(headers_locator)
                values = self.driver.find_elements_by_css_selector(values_locator)
                for header, value in zip(headers, values):
                    if header.text in allowed_heades:
                        single_data[header.text] = value.text
                output_names_birth_dates.append(single_data)
                new_search_button = self._wait_until(
                    new_search_button_locator,
                    by=By.XPATH
                )
                time.sleep(0.3)
                new_search_button.click()
    
        self._write_config_file('last_bookin_success', last_bookin_success)
        self._export_to_csv(output_names_birth_dates, 'DallasCounty')
        return output_names_birth_dates

    def dallascounty2_search(self):
        self.driver.get(self.web_pages['dallascounty'])
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en,en-US;q=0.9,es-419;q=0.8,es;q=0.7,es-ES;q=0.6,en-GB;q=0.5',
            'Host': 'www.dallascounty.org',
            'Origin': 'https://www.dallascounty.org',
            'Pragma': 'no-cache',
            'Referer': 'https://www.dallascounty.org/jaillookup/search.jsp',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36 Edg/85.0.564.51'
            
        }
        with requests.session() as conn:
            init_bookin_number = int(self._read_config_file('last_bookin_success',
                                                            '20018914'))
            model = {'Name': '', 'Race': '', 'Sex': '', 'DOB': '', 'Jail Location': '',
                               'Bookin Number': '', 'Bookin Date': '', 'Charge': '', 'Warrant Number': '',
                               'Magistrate': '', 'Remark': '',}
            allowerd_headers = list(model.keys())
            last_success = init_bookin_number
            base_url = 'https://www.dallascounty.org/jaillookup/'
            data = []
            for i in range(0,30):
                try:
                    single_data = model.copy()
                    bookin_number = init_bookin_number + i + 1
                    # 20019111
                    form_data = {'bookinNumber': bookin_number}
                    response = conn.post('https://www.dallascounty.org/jaillookup/searchByBookin',
                                        data=form_data,
                                        headers=headers,
                                        proxies=PROXY)
                    soup = BeautifulSoup(response.content)
                    link_element = soup.select_one('a.btn.btn-primary')
                    if link_element:
                        last_success = bookin_number
                        link = base_url + link_element.get('href')
                        response = conn.get(link, proxies=PROXY, headers=headers)
                        soup = BeautifulSoup(response.content)
                        meta_cells = soup.select('td[align=right]')
                        value_cells = soup.select('td[align=left]')
                        for header, value in zip(meta_cells, value_cells):
                            header = self._clean_string(header.get_text())
                            value = self._clean_string(value.get_text())
                            if header in allowerd_headers:
                                single_data[header] = value
                        data.append(single_data)
                except Exception:
                    print('sleeping')
                    time.sleep(1)
                    pass
            self._write_config_file('last_bookin_success', last_success)
            self._export_to_csv(data, 'DallasCounty')
            return data

    def sbcounty_booking_search(self):
        """Returns name and ages in this format:
        - [{'name': 'hisName', 'age': '33'}]"""
        self.driver.get(self.web_pages['sbcounty'])
        # Locators
        last_item_locator = "((//table[@class='BookingMain'])[4]//tr/td)[last()]/span"
        name_age_table_locator = 'div#grdResults_gridcontainer > table > tbody'
        # Here we bypass captcha
        last_item = self._wait_until(last_item_locator, by=By.XPATH)
        last_item.click()
        # Now we store name and ages
        output_names_ages = []
        name_age_table = self._wait_until(name_age_table_locator)
        rows = name_age_table.find_elements_by_tag_name('tr')
        for row in rows:
            cells = row.find_elements_by_tag_name('td')
            name = cells[0]
            age = cells[2]
            output_names_ages.append({
                'name': name.text,
                'age': age.text
            })
        self._export_to_csv(output_names_ages, 'sbcounty')
        return output_names_ages

    def tylerpaw_search(self):
        """Returns name, address, Attorneys, crime information, 
        and whether or not the page contains the word 'Arraignment' from
        taylerpaw page"""
        self.driver.get(self.web_pages['tylerpaw'])
        # Locators
        datefiled_option_locator = 'input#DateFiled'
        datefiled_after_locator = 'input#DateFiledOnAfter'
        datefiled_before_locator = 'input#DateFiledOnBefore'
        search_button_locator = 'input#SearchSubmit'
        criminal_record_link_locator = "//a[contains(text(),'Criminal')]"
        case_numbers_links_locator = 'tr > td >a'
        # Search
        today = datetime.date.today().strftime('%m/%d/%Y')
        # Today - one day = yesterday
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        yesterday = yesterday.strftime('%m/%d/%Y')
        criminal_record_link = self._wait_until(
            criminal_record_link_locator,
            by=By.XPATH
        )
        criminal_record_link.click()
        datefiled_option = self._wait_until(datefiled_option_locator)
        datefiled_after = self._wait_until(datefiled_after_locator)
        datefiled_before = self._wait_until(datefiled_before_locator)
        search_button = self._wait_until(search_button_locator)
        datefiled_option.click()
        datefiled_after.send_keys(yesterday)
        datefiled_before.send_keys(yesterday)
        search_button.click()
        case_numbers_links = self._wait_until(
            case_numbers_links_locator,
            until=EC.presence_of_all_elements_located
        )
        data = []
        for link_element in case_numbers_links:
            link = link_element.get_attribute('href')
            self._open_link_new_tab(link)
            details = self._tylerpaw_get_case_details()
            data.append(details)
        self._export_to_csv(data, 'taylerpaw')
        return data

    def azbar_search(self):
        self.driver.get(self.web_pages['azbar'])
        # Locators
        legal_need_input_locator = '#UserKeyword'
        county_option_locator = '#Maricopa'
        search_button_locator = "(//input[@class='green_btn'])[2]"
        next_button_locator = "//a[contains(text(), 'Next')]"
        last_page_locator = "//a[contains(text(), 'Last') and @class='current_page']"
        profile_description_locator = "section.profileDes"
        attorney_info_locator = 'p.oldRecord'
        # Fill search
        legal_need_input = self._wait_until(legal_need_input_locator)
        legal_need_input.send_keys('criminal defense')
        county_option = self._wait_until(county_option_locator)
        county_option.click()
        search_button = self._wait_until(search_button_locator, By.XPATH)
        search_button.click()
        last_page = False
        data = []
        links = []
        # Get all links
        while (last_page == False):
            attornies = self.driver.find_elements_by_css_selector(profile_description_locator)
            for attorney in attornies:
                name_link = attorney.find_element_by_css_selector('h3 > a')
                link = name_link.get_attribute('href')
                info = self._azbar_contact_info(link)
                data.append(info)
            # Hit next button until the end
            try:
                self.driver.find_element_by_xpath(last_page_locator)
                last_page = True
            except:
                next_button = self._wait_until(next_button_locator, By.XPATH)
                next_button.click()
            print(f'{len(data)} attorneys crawled.')
            self._export_to_csv(data, 'azbar')
        return data

    def floridabar_search(self):
        self.driver.get(self.web_pages['floridabar'])
        # Locators
        name_link_locator = 'p.profile-name > a'
        last_page_locator = 'li.inactive > i.fa-chevron-circle-right'
        next_button_locator = "a[title='next page']"
        # Search
        last_page = False
        data = []
        links = []
        while (not last_page):
            attornies = self.driver.find_elements_by_css_selector(name_link_locator)
            for attorney in attornies:
                link = attorney.get_attribute('href')
                links.append(link)
                # info = self._floridabar_single_info(link, headers)
                # data.append(info)
            # Hit next button until the end
            try:
                self.driver.find_element_by_css_selector(last_page_locator)
                last_page = True
            except:
                next_button = self._wait_until(next_button_locator)
                next_button.click()
        for counter, link in enumerate(links):
            if not counter % 50:
                print(f'{len(data) + 1} attorneys crawled.')
                print('Waiting 20 seconds to avoid being detected.')
                self._export_to_csv(data, 'floridabar')
                time.sleep(20)
            print(counter)
            time.sleep(1)
            info = self._floridabar_single_info_selenium(link)
            if info:
                data.append(info)
        self._export_to_csv(data, 'floridabar')

    def osceola_search(self):
        # self.driver.get('https://apps.osceola.org/Apps/CorrectionsReports/Report/Daily/2020-09-02')
        # self.driver.get(self.web_pages['osceola'])
        # Locators
        options_locator = '#date option'
        rows_locator = 'tbody tr'

        with requests.session() as conn:
            response = conn.get(self.web_pages['osceola'])
            soup = BeautifulSoup(response.content)
            options = soup.select(options_locator)
            dates = []
            for option in options:
                date_text = option.get_text()
                date = datetime.datetime.strptime(date_text, '%m/%d/%Y')
                formatted_date = datetime.datetime.strftime(date ,'%Y-%m-%d')
                dates.append(formatted_date)
            # Iterating dates to get the latest with data
            data = []
            for date in dates:
                response = conn.get(self.web_pages['osceola'] + date)
                soup = BeautifulSoup(response.content)
                rows = soup.select(rows_locator)
                if not rows:
                    continue
                for row in rows:
                    name = row.select_one('a.arrest-name').get_text()
                    dob = row.select_one('span.arrest-dob').get_text().replace('Birthdate: ', '')
                    statute = row.select_one('td.arrest-statute').get_text()
                    statute = self._clean_string(statute)
                    data.append({
                        'Name': name,
                        'Statute': statute,
                        'Date of birth': dob
                    })
                # Breaking, just need the last date successful
                break
            self._export_to_csv(data, 'osceola')
            return data
    
    def seminoleclerk_search(self):
        self.driver.get(self.web_pages['seminoleclerk'])
        # Locators
        from_date_locator = '#fromDateTxt'
        to_date_locator = '#toDateTxt'
        submit_locator = '#search'
        rows_locator = '#CaseGrid tbody tr'
        link_locator = 'a#CaseNum'

        to_date = datetime.datetime.now()
        from_date = to_date - datetime.timedelta(days=7)
        to_date_text = to_date.strftime('%m/%d/%Y')
        from_date_text = from_date.strftime('%m/%d/%Y')
        from_input = self._wait_until(from_date_locator)
        to_input = self._wait_until(to_date_locator)
        submit_button = self._wait_until(submit_locator)
        from_input.send_keys(from_date_text)
        to_input.send_keys(to_date_text)
        submit_button.click()
        self._wait_until('#CaseGrid')
        rows = self.driver.find_elements(By.CSS_SELECTOR, rows_locator)
        rows = rows[1:]
        data = []
        for row in rows:
            name = row.find_element(By.ID, 'caseStyle').text
            type_ = row.find_element(By.CSS_SELECTOR, 'td:nth-child(3)').text
            dob = row.find_element(By.CSS_SELECTOR, 'td:nth-child(4)').text
            file_date = row.find_element(By.CSS_SELECTOR, 'td:nth-child(5)').text
            charges = row.find_element(By.CSS_SELECTOR, 'td:nth-child(6)').text
            judge = row.find_element(By.CSS_SELECTOR, 'td:nth-child(7)').text
            status = row.find_element(By.CSS_SELECTOR, 'td:nth-child(8)').text
            link = row.find_element(By.CSS_SELECTOR, link_locator).get_attribute('href')
            dict_data = {
                'Name': name,
                'Type': type_,
                'Date of birth': dob,
                'File date': file_date,
                'Charges': charges,
                'Judge': judge,
                'Status': status,
                'link': link
            }
            data.append(dict_data)
        cookies = self.driver.get_cookies()
        for single_data in data:
            headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                'accept-encoding': 'gzip, deflate, br',
                'accept-language': 'en,en-US;q=0.9,es-419;q=0.8,es;q=0.7,es-ES;q=0.6,en-GB;q=0.5',
                'cache-control': 'no-cache',
                # 'cookie': '.ASPXANONYMOUS=UjcKvWIUUOLBPD0rO6O0TI9BplyRgNay6Yi932IP3Q_tiwXwtUcuH8lhMfYsIU-wa01HGDgB706ahNzkixiG2VTmuEADAvyPRbH5jeLinzfB9o3mCXO8bOFjWOdNuCuy0; ASP.NET_SessionId=tetxxdcvkw4yzkjjpkgq55pw; __AntiXsrfToken=39a7adadea6f4c948258afbdc28f8329',
                'pragma': 'no-cache',
                'referer': 'https://courtrecords.seminoleclerk.org/criminal/default.aspx',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'same-origin',
                'sec-fetch-user': '?1',
                'upgrade-insecure-requests': '1',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.135 Safari/537.36 Edg/84.0.522.63'
            }
            extra_data = self._seminoleclerk_get_extradata(single_data['link'], headers, cookies)
            single_data['Defendant Address'] = extra_data.get('address', 'Not available')
            single_data.pop('link')
            single_data['Has attorney'] = extra_data.get('has_attrny', 'NO ATTORNEY')
        self._export_to_csv(data, 'seminoleclerk')
        return data

    def ocfl_search(self):
        with requests.session() as conn:
            response = conn.get(self.web_pages['ocfl'])
            soup = BeautifulSoup(response.content)
            link = soup.select_one("a:contains('Daily Booking List')").get('href')
            # response = conn.get(link, stream=True)
            # response.raise_for_status()
            file_name = 'results/ocfl_pdf_file.pdf'
            if os.path.exists(file_name):
                os.remove(file_name)
            with closing(request.urlopen(link)) as r:
                with open(file_name, 'wb') as f:
                    shutil.copyfileobj(r, f)
            raw = parser.from_file(file_name)
            string_data = raw['content']
            pages = string_data.split('\n\n\n\n')
            data = []
            for page in pages:
                statements = page.split('\n')
                if len(statements) > 1:
                    statements = statements[11:]
                    for i, statement in enumerate(statements):
                        booking_re = r'(\d{8})'
                        date_re = r'([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})'
                        booking_match = re.findall(booking_re, statement)
                        date_match = re.findall(date_re, statement)
                        if booking_match:
                            booking_number = re.findall(
                                booking_re,
                                statement
                            )[0]
                            try:
                                release_date = re.findall(
                                    date_re,
                                    statement
                                )[0]
                                release_date = release_date[0] + '/' + release_date[1] + '/' + release_date[2]
                            except:
                                release_date = 'Not available'
                            try:
                                name = statement.split(booking_number)[0]
                                name = name[:-9]
                                place = statements[i + 2]
                                age = statements[i + 4]
                                race = statements[i + 6]
                                case = statements[i + 8].split(' ')[2]
                                county = statements[i + 8].split(' ')
                                county = ' '.join(county[3:])
                                statute = statements[i + 10]
                                data.append({
                                    'booking_number': booking_number,
                                    'release_date': release_date,
                                    'name': name,
                                    'place': place,
                                    'age': age,
                                    'race': race,
                                    'case': case,
                                    'county': county,
                                    'statute': statute
                                })
                            except:
                                pass
                    
            self._export_to_csv(data, 'ocfl')
            return data
        pass

    def jimspub_search(self):
        init_bookin_number = int(self._read_config_file('jimspub_number',
                                                        '202002545'))
        url = 'http://jimspub.riversidesheriff.org/cgi-bin/iisinfo.acu?bkno={0}'
        data = []
        for i in range(0, 200):
            single_data = {}
            url_bkin = url.format(init_bookin_number)
            self.driver.get(url_bkin)
            try:
                time.sleep(1)
                cells = self.driver.find_elements(By.CSS_SELECTOR, 'tbody td')
                single_data['booking_number'] = str(init_bookin_number)
                single_data['name'] = cells[6].text
                if cells[6].text == '':
                    raise
                single_data['sex'] = cells[10].text
                single_data['race'] = cells[11].text
                single_data['dob'] = cells[12].text
                single_data['age'] = cells[18].text
                single_data['hair'] = cells[19].text
                single_data['eyes'] = cells[20].text
                single_data['height'] = cells[21].text
                single_data['weight'] = cells[22].text
                single_data['arrest_date'] = cells[27].text
                single_data['arresting_agency'] = cells[29].text
                single_data['arresting_location'] = cells[30].text
                single_data['booked_date'] = cells[33].text
                single_data['case_no'] = cells[34].text
                single_data['current_facility'] = cells[39].text
                single_data['release_date'] = cells[48].text
                charges_text = cells[50].text
                charges_text = charges_text.replace('Charge Type', '')
                charges_text = charges_text.replace('Description', '')
                charges_text = charges_text.replace('Bail', '')
                charges_text = charges_text.replace('Disposition', '')
                charges_text = charges_text.replace('Type', '')
                charges_text = charges_text.replace('Booking', '')
                charges_text = self._clean_string(charges_text, ' | ')
                single_data['charges'] = charges_text
                data.append(single_data)
            except:
                pass
            init_bookin_number += 1
        self._write_config_file('jimspub_number', init_bookin_number)
        self._export_to_csv(data, 'jimspub')
        return data

    def quit_driver(self):
        """This closes chrome instance"""
        self.driver.quit()


if __name__ == '__main__':
    instant_defense = InstantDefense()
    try:
        execution = str(sys.argv[1])
    except:
        print('Not args given, executing all.')
        execution = 'all'
    if execution == 'ocsd':
        print(instant_defense.ocsd_submit_read_mail())
    elif execution == 'hcdistrictclerk':
        instant_defense.hcdistrictclerk_login()
    elif execution == 'dallascounty':
        print(instant_defense.dallascounty2_search())
    elif execution == 'sbcounty':
        print(instant_defense.sbcounty_booking_search())
    elif execution == 'tylerpaw':
        print(instant_defense.tylerpaw_search())
    elif execution == 'azbar':
        print(instant_defense.azbar_search())
    elif execution == 'floridabar':
        print(instant_defense.floridabar_search())
    elif execution == 'osceola':
        print(instant_defense.osceola_search())
    elif execution == 'seminoleclerk':
        print(instant_defense.seminoleclerk_search())
    elif execution == 'ocfl':
        print(instant_defense.ocfl_search())
    elif execution == 'jimspub':
        print(instant_defense.jimspub_search())
    elif execution == 'all':
        print('******************')
        print('Submitting form...')
        print(instant_defense.ocsd_submit_read_mail())
        print('Login to hcdistrictclerk.')
        instant_defense.hcdistrictclerk_login()
        print('Dallascounty bookin search.')
        print(instant_defense.dallascounty_bookin_search())
        print('Sbcounty list search')
        print(instant_defense.sbcounty_booking_search())
        print(instant_defense.tylerpaw_search())
        print(instant_defense.azbar_search())
        print(instant_defense.floridabar_search())
        print(instant_defense.osceola_search())
        print(instant_defense.ocfl_search())
    else:
        print('Invalid method, see the valid ones:')
        print('ocsd')
        print('hcdistrictclerk')
        print('dallascounty')
        print('sbcounty')
        print('all')
    instant_defense.quit_driver()
