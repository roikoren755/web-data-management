import sys
import re
import requests
import unicodedata
import urllib
import lxml.html
import rdflib
from rdflib import URIRef, Literal, XSD

base_url = 'https://en.wikipedia.org'
url = '%s/wiki/List_of_countries_by_population_(United_Nations)' % base_url
graph = rdflib.Graph()
president_property = URIRef('http://example.org/property/president')
prime_minister_property = URIRef('http://example.org/property/prime_minister')
population_property = URIRef('http://example.org/property/population')
area_property = URIRef('http://example.org/property/area')
government_property = URIRef('http://example.org/property/government')
capital_property = URIRef('http://example.org/property/capital')
birth_date_property = URIRef('http://example.org/property/birth_place')


def create_ontology_entry(path):
    if 'index.php' in path:  # If the page of the person/country doesn't exist, this will be in the path
        path = '/%s' % path.split('title=')[-1].split('&')[0]  # Take the name (and just the name) from the path
    # Take everything after the last / (the name itself), and convert things like %C3%A9 to é
    name = urllib.parse.unquote(path.split('/')[-1])
    name = name.replace('_', ' ')  # Humanize name, Donald_Trump => Donald Trump
    name = name.split('(')[0].strip()  # Remove (politician) and spacings
    # Convert things like é to e
    nkfd_form = unicodedata.normalize('NFKD', name)
    name = u"".join([c for c in nkfd_form if not unicodedata.combining(c)])
    return Literal(name, datatype=XSD.string)


def crawl_person_page(person_path):
    person_url = '%s%s' % (base_url, person_path)
    response = requests.get(person_url)
    doc = lxml.html.fromstring(response.content)
    infobox = doc.xpath("//table[contains(@class, 'infobox')][1]")
    if len(infobox) == 0:
        return  # No infobox, nothing to crawl

    infobox = infobox[0]
    birth_date_xpath = "./tbody/tr[./th[contains(text(), 'Born')]]/td//span[contains(@class, 'bday')]/text()"
    birth_date = infobox.xpath(birth_date_xpath)
    if len(birth_date) > 0:  # If person's infobox contains birth date, add to ontology
        birth_date = infobox.xpath(birth_date_xpath)[0].strip()
        birth_date_ref = Literal(birth_date, datatype=XSD.date)
        person_ref = create_ontology_entry(person_path)
        graph.add((person_ref, birth_date_property, birth_date_ref))


def crawl_country_page(country_path):
    country_ref = create_ontology_entry(country_path)
    country_url = '%s%s' % (base_url, country_path)
    response = requests.get(country_url)
    doc = lxml.html.fromstring(response.content)
    infobox = doc.xpath("//table[contains(@class, 'infobox')][1]/tbody")[0]  # Get infobox

    # XPath to get person from countries infobox, by title, assuming the title does not contain the word Vice (VP)
    person_xpath_template = "./tr[./th//a[contains(text(), '%s') and not(contains(text(), 'Vice'))]]/td" \
                            "//a[not(contains(@href, 'cite_note'))]/@href"

    president_xpath = person_xpath_template % 'President'  # XPath to president wiki page
    president = infobox.xpath(president_xpath)
    if len(president) > 0:  # Got a president!
        # These are special cases, of 'countries' under french rule, that have both the french president and their own
        # in the infobox...
        if country_path == '/wiki/French_Polynesia' or country_path == '/wiki/New_Caledonia' \
                or country_path == '/wiki/Wallis_and_Futuna' or country_path == '/wiki/Saint_Pierre_and_Miquelon':
            president = president[-1]
        # For everyone else, the first is the only one there
        else:
            president = president[0]
        president_ref = create_ontology_entry(president)
        graph.add((country_ref, president_property, president_ref))
        crawl_person_page(president)

    # Premier === Prime Minister, either one or the other appear, never both
    has_prime_minister = False
    premier_xpath = person_xpath_template % 'Premier'
    premier = infobox.xpath(premier_xpath)
    prime_minister_xpath = person_xpath_template % 'Prime Minister'
    prime_minister = infobox.xpath(prime_minister_xpath)
    if len(prime_minister) > 0:
        prime_minister = prime_minister[0]
        has_prime_minister = True
    elif len(premier) > 0:
        prime_minister = premier[0]
        has_prime_minister = True
    if has_prime_minister:
        prime_minister_ref = create_ontology_entry(prime_minister)
        graph.add((country_ref, prime_minister_property, prime_minister_ref))
        crawl_person_page(prime_minister)

    # XPath to get property from infobox, like area or population
    property_xpath_template = \
        "./tr[./th/descendant-or-self::*[contains(text(), '%s')]]/following-sibling::tr[1]/td//text()"

    population_xpath = property_xpath_template % 'Population'
    # Remove citations and parenthesised references, like rankings
    population = infobox.xpath(population_xpath)[0].split('(')[0].strip()
    population_ref = Literal(population, datatype=XSD.string)
    graph.add((country_ref, population_property, population_ref))

    area_xpath = property_xpath_template % 'Area'
    # Remove km if exists, leaving us with a human-readable number
    area = infobox.xpath(area_xpath)[0].replace('km', '').strip()
    area = area + ' km2'
    # Damn yanks and their miles. Only countries I saw where the first number is in square miles rather than km^2
    if country_path == '/wiki/United_States' or country_path == '/wiki/Guam':
        area = area.split('(')[-1].strip()
    area_ref = Literal(area, datatype=XSD.string)
    graph.add((country_ref, area_property, area_ref))

    government_xpath = \
        "./tr[./th/descendant-or-self::*[contains(text(), 'Government') and not(contains(text(), 'seat'))]]/td//text()"
    government_parts = infobox.xpath(government_xpath)
    # Remove references from government type, which comprises several links and text parts
    government = ' '.join([part for part in government_parts if '[' not in part])
    # Swap all whitespaces with a single space per group
    government = re.sub(r'\s+', ' ', government)
    # Sometimes there isn't a government type...
    if government != '':
        government_ref = Literal(government, datatype=XSD.string)
        graph.add((country_ref, government_property, government_ref))

    capital_xpath = "./tr[./th[contains(text(), 'Capital')]]/td//a/text()"
    capital = infobox.xpath(capital_xpath)
    # Sometimes there's no capital, either!
    if len(capital) > 0:
        capital = capital[0]
        # Countries like Monaco, Singapore and Vatican City, the link's text is city-state...
        if capital == 'city-state':
            capital = country_path.split('/wiki/')[-1]
        # Switzerland doesn't have a capital as of the time of writing. If it changes, this won't be necessary
        elif capital == 'de jure':
            capital = 'None'
        # Last but not least, Tokelau, which is a country, apparently, hadn't decided on a capital...
        elif country_path == '/wiki/Tokelau' and capital == '[a]':
            capital = 'Undetermined'
        capital_ref = Literal(capital, datatype=XSD.string)
        graph.add((country_ref, capital_property, capital_ref))


def create_ontology(file_name):
    response = requests.get(url)
    doc = lxml.html.fromstring(response.content)
    countries = doc.xpath("//table[contains(@class, 'sortable')][1]/tbody/tr/td[2]/a/@href")
    # Go over all countries, crawling each one's wikipedia page
    for country in countries:
        crawl_country_page(country)
    # Save ontology to file
    graph.serialize(file_name, format='nt')


if __name__ == '__main__':
    args = sys.argv
    if len(args) < 3:
        print('USAGE:')  # TODO - add usage
    elif args[1] == 'create':
        if len(args) > 3:
            print('USAGE:')  # TODO - add usage
        else:
            create_ontology(args[2])
    elif args[1] == 'question':
        answer_question(' '.join(args[2:])) # TODO - implement
    else:
        print('USAGE:')  # TODO - add usage
