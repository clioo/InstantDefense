from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import sys
import time


OUTLOOK_EMAIL = 'instant_defense1@outlook.com'
OUTLOOK_PASSWORD = 'yNY9n2PHs*Tu#Sp)'
HCDISTRICTCLERK_EMAIL = 'pkaster@usc.edu'
HCDISTRICTCLERK_PASSWORD = 'yNY9n2PHs*Tu#Sp)'


class InstantDefense:

    def __init__(self, debug=False):
        self.web_pages = {
            'ocsd': 'http://ws.ocsd.org/ArrestLog/ArrestLogMain.aspx',
            'hcdistrictclerk': 'https://www.hcdistrictclerk.com/edocs/public/search.aspx?newsuits=1',
            'outlook': 'https://outlook.live.com/mail/0/',
            'dallascounty': 'https://www.dallascounty.org/jaillookup/search.jsp',
            'sbcounty': 'http://web.sbcounty.gov/sheriff/bookingsearch/bookingsearch.aspx'
        }
        # Default wait time in seconds
        debug = True
        if debug:
            # This will open the browser, just for debugging
            # purposes
            self.driver = webdriver.Chrome()
            self.driver.maximize_window()
        else:
            # Open the browser in the background, this is used
            # in servers that have no GUI
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920x1080')
            self.driver = webdriver.Chrome(options=options)

    # Private methods
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
        # Submit the form and read the sent email
        submit_button_selector = '#btnSearch'
        email_input_selector = '#txtEmail'
        invalid_email_selector = '#lblMessage'
        # Submit the form
        self.driver.get(self.web_pages['ocsd'])
        submit_button = self._wait_until(submit_button_selector)
        submit_button.click()
        email_input = self._wait_until(email_input_selector)
        email_input.send_keys(OUTLOOK_EMAIL)
        submit_button = self._wait_until(submit_button_selector)
        submit_button.click()
        self._wait_until(invalid_email_selector)

    def _read_last_email(self):
        # Locators
        log_in_link_selector = 'nav.auxiliary-actions > ul a.sign-in-link, div.c-group.links :nth-child(2) > a'
        email_input_selector = 'input[type=email]'
        password_input_selector = 'input[type=password]'
        next_button_selector = 'input[type=submit]'
        sign_in_button_selector = 'input[type=submit]'
        mails_selector = 'div[role=option]'
        body_mail_selector = 'div.wide-content-host > div > div + div > div'
        # Let's read the last mail mail !
        self.driver.get(self.web_pages['outlook'])
        log_in_link = self._wait_until(log_in_link_selector)
        log_in_link.click()
        email_input = self._wait_until(email_input_selector)
        email_input.send_keys(OUTLOOK_EMAIL)
        next_button = self._wait_until(next_button_selector)
        next_button.click()
        password_input = self._wait_until(password_input_selector)
        password_input.send_keys(OUTLOOK_PASSWORD)
        sign_in_button = self._wait_until(sign_in_button_selector)
        sign_in_button.click()
        mail = self._wait_until(mails_selector)
        mail.click()
        body_mail = self._wait_until(body_mail_selector)
        return body_mail.text
    
    # Public methods
    def ocsd_submit_read_mail(self):
        self._ocsd_submit()
        self._read_last_email()

    def hcdistrictclerk_login(self):
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
        email_input.send_keys(HCDISTRICTCLERK_EMAIL)
        password_input.send_keys(HCDISTRICTCLERK_PASSWORD)
        login_button.click()

    def dallascounty_bookin_search(self):
        """Using a for loop to do the bookin search.
        Output format (list of dictionaries):
            - [{'name': 'Name 1', 'birth_date': '1969-07-20'}]"""
        self.driver.get(self.web_pages['dallascounty'])
        # Locators
        bkin_num_input_locator = 'input[name=bookinNumber]'
        search_button_locator = 'form[name=searchByBookin] input[type=submit]'
        wrong_message_locator = 'div.alert-danger'
        new_search_button_locator = "//input[contains(@value, 'New Search')]"
        name_link_locator = 'a.btn-primary'
        birth_date_locator = 'table.table > tbody > tr :nth-child(4)'
        # We start searching
        bkin_num_input = self._wait_until(bkin_num_input_locator)
        search_button = self._wait_until(search_button_locator)
        output_names_birth_dates = []
        init_bookin_number = int(self._read_config_file('last_bookin_success',
                                                        '20018914'))
        last_bookin_success = int(init_bookin_number)
        for i in range(0, 100):
            time.sleep(0.5)
            bkin_number = init_bookin_number + i
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
                output_names_birth_dates.append({
                    'name': name,
                    'birth_date': birth_date
                })
                new_search_button = self._wait_until(
                    new_search_button_locator,
                    by=By.XPATH
                )
                time.sleep(0.3)
                new_search_button.click()
    
        self._write_config_file('last_bookin_success', last_bookin_success)
        return output_names_birth_dates

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
        return output_names_ages
        pass

    def quit_driver(self):
        self.driver.quit()


if __name__ == '__main__':
    instant_defense = InstantDefense(True)
    try:
        execution = str(sys.argv[1])
    except:
        print('Not args given, executing all.')
        execution = 'all'
    if execution == 'ocsd':
        instant_defense.ocsd_submit_read_mail()
    elif execution == 'hcdistrictclerk':
        instant_defense.hcdistrictclerk_login()
    elif execution == 'dallascounty':
        instant_defense.dallascounty_bookin_search()
    elif execution == 'sbcounty':
        instant_defense.sbcounty_booking_search()
    elif execution == 'all':
        print('******************')
        print('Submiting form...')
        print('Reading email...')
        print(instant_defense.ocsd_submit_read_mail())
        print('Login to hcdistrictclerk.')
        instant_defense.hcdistrictclerk_login()
        print('Dallascounty bookin search.')
        print(instant_defense.dallascounty_bookin_search())
        print('Sbcounty list search')
        print(instant_defense.sbcounty_booking_search())
    else:
        print('Invalid method, see the valid ones:')
        print('ocsd')
        print('hcdistrictclerk')
        print('dallascounty')
        print('sbcounty')
        print('all')
    instant_defense.quit_driver()