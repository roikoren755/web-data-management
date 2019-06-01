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


USAGE = '''
USAGE: To create the ontology, run `python %s create FILE_NAME`.
       To query the ontology after creation, run `python %s question YOUR QUESTION HERE`
'''


def create_ontology_entry(path):
    if 'index.php' in path:  # If the page of the person/country doesn't exist, this will be in the path
        path = '/wiki/%s' % path.split('title=')[-1].split('&')[0]  # Take the name (and just the name) from the path
    # Convert things like %C3%A9 to é
    name = urllib.parse.unquote(path)
    name = name.split('(')[0].strip()  # Remove (politician) and spacings
    # Convert things like é to e
    nkfd_form = unicodedata.normalize('NFKD', name)
    name = u"".join([c for c in nkfd_form if not unicodedata.combining(c)])
    # return Literal(name, datatype=XSD.string)
    return URIRef('%s%s' % (base_url, name))


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


def crawl_country_page(country_path, country_name):
    country_ref = create_ontology_entry(country_name)
    country_url = '%s%s' % (base_url, country_path)
    response = requests.get(country_url)
    doc = lxml.html.fromstring(response.content)
    infobox = doc.xpath("//table[contains(@class, 'infobox')][1]/tbody")[0]  # Get infobox

    # XPath to get person from country's infobox, by exact title, the title being the link's text
    person_xpath_template = "./tr[./th//a[text() = '%s']]/td//a[not(contains(@href, 'cite_note'))]/@href"

    president_xpath = person_xpath_template % 'President'  # XPath to president wiki page
    president = infobox.xpath(president_xpath)
    if len(president) > 0:  # Got a president!
        president = president[0]
        president_ref = create_ontology_entry(president)
        graph.add((country_ref, president_property, president_ref))
        crawl_person_page(president)

    prime_minister_xpath = person_xpath_template % 'Prime Minister'  # XPath to prime minister wiki page
    prime_minister = infobox.xpath(prime_minister_xpath)
    if len(prime_minister) > 0:
        prime_minister = prime_minister[0]
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
    if 'de jure' in government or 'de facto' in government:
        split_government = government.split('de jure')
        government = split_government[0].strip() if split_government[0] != '' else split_government[1].strip()
        if government.startswith(':') and 'de facto' in government:
            government = government.split('de facto')[0][1:].strip()
        if government.endswith('('):
            government = government[:-1]
    if 'with a de facto' in government:
        government = government.split('with a de facto')[0].strip()
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
    countries = doc.xpath("//table[contains(@class, 'sortable')][1]/tbody/tr/td[2]/a")
    # Go over all countries, crawling each one's wikipedia page
    for country in countries:
        country_link = country.xpath("./@href")[0]
        country_name = '/wiki/%s' % country.xpath("./text()")[0].replace(' ', '_')
        if country_name == '/wiki/Congo':
            country_name = country_link
        crawl_country_page(country_link, country_name)
    # Save ontology to file
    graph.serialize(file_name, format='nt')


def humanize(ref):
    return ('%s' % ref).split('/')[-1].replace('_', ' ')


def answer_question(question):
    what_to_property = {'president': president_property, 'prime minister': prime_minister_property,
                        'population': population_property, 'area': area_property, 'government': government_property,
                        'capital': capital_property}
    graph.parse('ontology.nt', format='nt')
    query = ''

    match = re.fullmatch('Who is the (president|prime minister) of ([^?]+)\\?', question)
    if match is not None:
        who = match.group(1)
        who_property = president_property if who == 'president' else prime_minister_property
        country = '%s/wiki/%s' % (base_url, match.group(2).replace(' ', '_'))
        query = 'select distinct ?person where { <%s> <%s> ?person }' % (country, who_property)

    match = re.fullmatch('What is the (population|area|government|capital) of ([^?]+)\\?', question)
    if match is not None and query == '':
        what = match.group(1)
        what_property = what_to_property[what]
        country = '%s/wiki/%s' % (base_url, match.group(2).replace(' ', '_'))
        query = 'select distinct ?property where { <%s> <%s> ?property }' % (country, what_property)

    match = re.fullmatch('When was the (president|prime minister) of ([^?]+) born\\?', question)
    if match is not None and query == '':
        who = match.group(1)
        who_property = what_to_property[who]
        country = '%s/wiki/%s' % (base_url, match.group(2).replace(' ', '_'))
        query = 'select distinct ?date where { <%s> <%s> ?p . ?p <%s> ?date}' % (country, who_property,
                                                                                 birth_date_property)

    match = re.fullmatch('Who is ([^?]+)\\?', question)
    if match is not None and query == '':
        who = '%s/wiki/%s' % (base_url, match.group(1).replace(' ', '_'))
        query_format = 'select distinct ?c where { ?c <%s> <%s> }'
        queries = {'president': query_format % (president_property, who),
                   'prime minister': query_format % (prime_minister_property, who)}

        res = sorted(list(graph.query(queries['president'])))
        if len(res) > 0:
            who = 'President'
        else:
            res = sorted(list(graph.query(queries['prime minister'])))
            if len(res) == 0:
                print('Could not figure out who he is :(')
                return
            who = 'Prime minister'
        list_of_countries = [humanize(c[0]) for c in res]
        answer = '%s of %s' % (who, ', '.join(list_of_countries))
        print(answer)
        return answer
    else:
        res = list(graph.query(query))
        if len(res) == 0:
            print('Could not figure that one out :(')
            return
        answer = humanize(list(graph.query(query))[0][0])
        print(answer)
        return answer


def q2():
    graph.parse('ontology.nt', format='nt')
    query1 = 'select (count(distinct ?p) as ?prime_ministers) where { ?c <%s> ?p }' % prime_minister_property
    print(query1)
    res = list(graph.query(query1))
    print(res[0][0])

    query2 = 'select (count(distinct ?c) as ?countries) where { ?c <%s> ?p }' % population_property
    print(query2)
    res = list(graph.query(query2))
    print(res[0][0])

    query3 = 'select (count(distinct ?c) as ?countries) where { ?c <%s> ?g .' \
             '                                                  filter regex(str(?g), "[Rr]epublic")}' % government_property
    print(query3)
    res = list(graph.query(query3))
    print(res[0][0])

    query4 = 'select (count(distinct ?c) as ?countries) where { ?c <%s> ?g .' \
             '                                                  filter regex(str(?g), "[Mm]onarchy")}' % government_property
    print(query4)
    res = list(graph.query(query4))
    print(res[0][0])


if __name__ == '__main__':
    args = sys.argv
    usage = USAGE % (args[0], args[0])
    if len(args) == 2 and args[1] == 'q2':
        q2()
    elif len(args) < 3:
        print(usage)
    elif args[1] == 'create':
        if len(args) > 3:
            print(usage)
        else:
            create_ontology(args[2])
    elif args[1] == 'question':
        answer_question(' '.join(args[2:]))
    else:
        print(usage)
