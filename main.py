import csv
import re

import requests
import warnings
from os.path import basename, dirname
from bs4 import BeautifulSoup
from cv2 import VideoCapture, CAP_PROP_FRAME_COUNT, CAP_PROP_FPS

FILENAME = 'films'
SUPPORTED_EXTENSIONS = ['csv']
WEBPAGE_PREFIX = 'https://lumiere.berkeley.edu'


class MediaFile:
    disclaimer = 'The copyright law of the United States (Title 17 U.S. Code) governs the making of photocopies or ' \
                 'other reproductions of copyrighted material. This content is provided exclusively by streaming for ' \
                 'course assigned viewing during the current semester or quarter. Users are liable for any ' \
                 'infringement, including reproduction, capture, download, copying or redistribution. '

    def __init__(self, url):
        assert WEBPAGE_PREFIX in url, f'Unable to process url: {url}'
        self.url = url
        self.id = self.url.rsplit('/', 1)[-1]
        raw = requests.get(url).text

        main_page = BeautifulSoup(raw, 'html.parser')

        self.title = main_page.find(class_=re.compile(r'(page-title)\s.*')).string.strip()

        self.media_url = WEBPAGE_PREFIX + main_page.find('video')['src']
        clip = VideoCapture(self.media_url)
        self.duration = int((clip.get(CAP_PROP_FRAME_COUNT) / clip.get(CAP_PROP_FPS)) // 60)

        self.has_subtitles = bool(re.sub(r'(?i)(subtitle:)\s*', '', main_page.find(class_='dk').string))
        if self.has_subtitles:
            self.subtitles = main_page.find()
        else:
            self.subtitles = None

        film_info = BeautifulSoup(requests.get(url + '/film_info').text, 'html.parser')

        attrs = [x for x in film_info.find('span', class_='dk').parent.text.split('\n') if x]
        dct = {}

        while len(attrs) >= 2:
            item = attrs[0]
            if item[len(item) - 1] == ':':
                make_attr = re.sub(r'\s', '_', item.lower())[:len(item) - 1]
                if re.findall(r'(,|\b/\b)', attrs[1]):
                    dct[make_attr] = [x.strip() for x in re.sub(r'[,/]', '!', attrs[1]).split('!')]
                else:
                    dct[make_attr] = attrs[1]
            attrs = attrs[1:]

        for key in dct:
            self.__setattr__(key, dct[key])
            if key == 'purchased_at':
                self.__setattr__(key, re.findall(r'(?<=[(http|https)][(://)][(www.)])[\w-]+\.(com|net|org|co|us)', self.__dict__[key]))


        synopsis = film_info.find('h3', text='Synopsis').parent.text.split('\n', 2)[2:]

        if len(synopsis) > 0:
            self.synopsis = re.sub(r'(\\)', '', re.sub(r'((\\n)|(\\r))+', ' ', synopsis[0].__repr__()[1:-1]))
        else:
            self.synopsis = None

        if len(self.__dict__) != 14:
            warnings.warn(f'object contains {len(self.__dict__)} attributes rather than 14')

    def __str__(self):
        return f'{self.title} from {self.url}'

    def __repr__(self):
        def list_to_str(lst):
            if isinstance(lst, list):
                return ', '.join(lst)
            return lst

        return ''.join([f'{key.upper()}: {list_to_str(self.__dict__[key])}\n' for key in self.__dict__])

    def num_attrs(self):
        return len(self.__dict__)


def input_looper(prompt, type_, options=None):
    while True:
        try:
            selection = type_(input(prompt))
            if options:
                assert selection in options, 'Unsupported type: ' + str(selection)
        except ValueError or AssertionError:
            print('Please enter a valid input.')
            continue
        else:
            break
    return selection


def logger(file_type, objs):
    print(f'"{FILENAME}" successfully loaded from previous session.')
    if file_type == 'csv':
        with open(FILENAME + '.' + file_type, 'r+', newline='', encoding='latin-1') as file:
            attrs = [x for x in objs[0].__dict__.keys()]
            additions = []
            lst = list(csv.reader(file, delimiter=','))
            writer = csv.writer(file, delimiter=',')

            if not lst:
                writer.writerow(attrs)

            for obj in objs:
                addition = [obj.__dict__[attr] for attr in attrs]
                if addition not in list(csv.reader(file, delimiter=',')):
                    additions.append(addition)
                else:
                    warnings.warn(f'{obj.id} already present in "{FILENAME}"', category=UserWarning)

            writer.writerows(additions)


def make_requests(start, stop, sleep_time=0.2, logging=None):
    def int_corrector(num):
        if num < 10:
            num = '0000' + str(num)
        elif num < 100:
            num = '000' + str(num)
        elif num < 1000:
            num = '00' + str(num)
        elif num < 10000:
            num = '0' + str(num)
        else:
            num = int(num)
        return int(num)

    start = int_corrector(start)
    stop = int_corrector(stop)

    from time import process_time, sleep
    start_time = process_time()
    successes = 0
    failures = 0
    successes_list = []
    fails_list = []

    line_breaker = '-----------------------------------------------------------------------'
    n = '\n'
    while start < stop:
        try:
            print(WEBPAGE_PREFIX + f'/students/items/{str(start)}')
            media_file = MediaFile(WEBPAGE_PREFIX + f'/students/items/{str(start)}')
            successes_list.append(media_file)
            start += 1
            successes += 1
        except TypeError:
            fails_list += [str(start)]
            start += 1
            failures += 1
            warnings.warn(f'Lumiere media item "{start}" not found')
            continue

        print(f'{line_breaker}\nRequested "{media_file.title}" from {media_file.url}\nNumber of Attributes: {len(media_file.__dict__)}\n{(lambda x: n.join(x))(media_file.__repr__().splitlines())}')

    if logging:
        logger(logging, successes_list)
        with open('failed_ids.txt', 'w+') as ids:
            ids.writelines(fails_list)
        print(line_breaker + '\nData successfully saved.\n' + line_breaker)

    sleep(sleep_time)
    print(fails_list)
    difference = round(process_time() - start_time, 3)

    if successes:
        print(f'{n}Successfully processed {successes} queries in {round(difference + successes * sleep_time, 3)}s ({round(difference / successes, 3)}s per query).'
              f'\nFailed to process {failures} queries.\n')
    else:
        print('\nFailed to process any queries.\n')


def main():
    print(f'=====[{basename(dirname(__file__))} by Julian Bixler]=====')
    num_vars = 0
    #file_type = input_looper(f'File extension to save {num_vars} objects (must be of type {(lambda x: ", ".join(x))(SUPPORTED_EXTENSIONS)}):', str, SUPPORTED_EXTENSIONS)
    #start = input_looper('Starting ID of requests to be made:', int)
    #stop = input_looper('Ending ID of requests to be made:', int)
    #sleep_time = round(input_looper('HTTP requests per second:', int) ** (-1), 2)

    make_requests(48028, 48029, 0, logging='csv')


if __name__ == '__main__':
    main()
