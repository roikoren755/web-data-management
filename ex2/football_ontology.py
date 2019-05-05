import sys
import requests
import lxml.html
import rdflib
from rdflib import URIRef, Literal, XSD

base_path = 'https://en.wikipedia.org'
graph = rdflib.Graph()
country_property = URIRef('http://example.org/property/country')
league_property = URIRef('http://example.org/property/league')
homeCity_property = URIRef('http://example.org/property/homeCity')
playsFor_property = URIRef('http://example.org/property/playsFor')
birthPlace_property = URIRef('http://example.org/property/birthPlace')
located_in_property = URIRef('http://example.org/property/located_in')
birthDate_property = URIRef('http://example.org/property/birthDate')
position_property = URIRef('http://example.org/property/position')


def get_ontology_entry(ref):
    # Add base path to all ontology entries
    return URIRef(base_path + ref)


def get_country_from_league_page(league_relative_path):
    """
    Returns country where league is played
    :param league_relative_path: a /wiki/SOME_LEAGUE_PAGE formatted string for the league's wikipedia page
    :return: the name of the country where the league is played
    """
    url = base_path + league_relative_path
    response = requests.get(url)
    doc = lxml.html.fromstring(response.content)
    country_xpath = "//table[contains(@class, 'infobox')][1]/descendant::th[contains(text(), 'Country')]" \
                    "/parent::tr/td/text()"

    return doc.xpath(country_xpath)[0].strip()


def get_country_from_city_page(city_relative_path):
    """
    Returns country where city is located
    :param city_relative_path: a /wiki/SOME_CITY_PAGE formatted string for the city's wikipedia page
    :return: the name of the country where the city is located
    """
    city = city_relative_path.split('/')[-1]
    if city == 'West_Berlin':
        return '/wiki/Germany'  # These cities' pages proved difficult to crawl...
    elif city == 'S%C3%A9dhiou':
        return '/wiki/Senegal'
    elif city == 'La_Plata':
        return '/wiki/Argentina'
    elif city == 'Santa_Rita_do_Sapuca%C3%AD':
        return '/wiki/Brazil'
    elif city == 'Gortnahoe':
        return '/wiki/Ireland'
    elif city == '/wiki/Arguinegu%C3%ADn':
        return '/wiki/Spain'
    url = base_path + city_relative_path
    response = requests.get(url)
    doc = lxml.html.fromstring(response.content)
    infobox = doc.xpath("//table[contains(@class, 'infobox')][1]")
    if len(infobox) > 0:  # Found the infobox!
        infobox = infobox[0]
    # Sometimes, in the nav-box at the bottom of the page, the country can appear
    elif len(doc.xpath("//table[contains(@class, 'navbox-inner')][1]//th/div/a/@href")) > 0:
        return doc.xpath("//table[contains(@class, 'navbox-inner')][1]//th/div/a/@href")[-1]
    # If we got here, it's probably a stub
    else:
        stub_xpath = "//table[contains(@class, 'stub')][1]//td/i/a/@href[1]"  # This ${COUNTRY} related article is a stub
        stub = doc.xpath(stub_xpath)
        if len(stub) > 0:
            return stub[0]
        else:
            # Couldn't even find that
            print('OOOPSSS')
            return '/wiki/OOOPSSS'
    constituent_country = infobox.xpath(".//*[contains(text(), 'Constituent country')]/ancestor::tr/td")
    #  Sometimes appears under Constituent country
    if len(constituent_country) > 0:
        link = constituent_country[0].xpath(".//a/@href")
        # If there's a link, return it, otherwise create link from name of country
        return link[0] if len(link) > 0 else '/wiki/' + constituent_country[0].xpath(".//text()")[0].strip().replace(
            ' ', '_')
    country = infobox.xpath(
        "./tbody/tr/th/descendant-or-self::*[contains(text(), 'Country') or contains(text(), 'country')]/ancestor::tr/td")
    # Simplest case - found country in infobox
    if len(country) > 0:
        country = country[0]
    # The link will say districts of COUNTRY
    elif len(infobox.xpath(".//*[contains(text(), 'District')]/@href")) > 0:
        link = infobox.xpath(".//*[contains(text(), 'District')]/@href")[0].split('_')[-1]
        return '/wiki/' + link
    # Regions of COUNTRY
    elif len(infobox.xpath(".//*[contains(text(), 'Region')]/@href")) > 0:
        link = infobox.xpath(".//*[contains(text(), 'Region')]/@href")[0].split('_')[-1]
        return '/wiki/' + link
    # Provinces of COUNTRY
    elif len(infobox.xpath(".//*[contains(text(), 'Province')]/@href")) > 0:
        link = infobox.xpath(".//*[contains(text(), 'Province')]/@href")[0].split('_')[-1]
        return '/wiki/' + link
    # Sometimes a link to the country's census is available, and will look like Census_in_COUNTRY#YEAR
    else:
        country = doc.xpath("//a[contains(@href, 'Census')]/@href")[0].split('Census_in_')[-1].split('#')[0]
        return '/wiki/' + country
    link = country.xpath(".//a/@href")
    # If it's in a link, get it, otherwise generate one from the name
    return link[-1] if len(link) > 0 else '/wiki/' + country.xpath(".//text()")[0].strip().replace(' ', '_')


def crawl_player_page(player_relative_path):
    """
    Crawls given player page, extracting necessary data
    :param player_relative_path: a /wiki/SOME_PLAYER_PAGE formatted string for the player's wikipedia page
    :return: None
    """
    player_ref = get_ontology_entry(player_relative_path)
    url = base_path + player_relative_path
    response = requests.get(url)
    doc = lxml.html.fromstring(response.content)
    # Get infobox
    infobox = doc.xpath("//table[contains(@class, 'infobox')][1]/tbody")
    if len(infobox) == 0:
        print('player %s does not have an infobox!' % player_relative_path)
        return
    infobox = infobox[0]
    dob_xpath = "./tr/th[contains(text(), 'Date of birth')]/ancestor::tr/td//span[contains(@class, 'bday')]/text()"
    # Get DoB
    date_of_birth = infobox.xpath(dob_xpath)[0].strip()
    dob_ref = Literal(date_of_birth, datatype=XSD.date)
    graph.add((player_ref, birthDate_property, dob_ref))
    birth_place_xpath = "./tr/th[contains(text(), 'Place of birth')]/ancestor::tr/td/a/@href"
    player = player_relative_path.split('/')[-1]
    # Place of birth exists as link
    if len(infobox.xpath(birth_place_xpath)) > 0:
        birth_place = infobox.xpath(birth_place_xpath)[0].strip()
        birth_place_ref = get_ontology_entry(birth_place)
        graph.add((player_ref, birthPlace_property, birth_place_ref))
        # These players' place of birth is already a country!
        if player != 'Grady_Diangana' and player != 'Ben_Johnson_(footballer,_born_2000)':
            country = get_country_from_city_page(birth_place).strip()
            country_ref = get_ontology_entry(country)
            graph.add((birth_place_ref, located_in_property, country_ref))
    # These players don't have place of birth at all...
    elif player != 'Kayne_Ramsay' and player != 'Conor_Coventry':
        birth_place = infobox.xpath("./tr/th[contains(text(), 'Place of birth')]/ancestor::tr/td/text()")[0].strip() \
            .replace(' ', '_')
        birth_place_ref = get_ontology_entry('/wiki/' + birth_place)
        graph.add((player_ref, birthPlace_property, birth_place_ref))
    position_xpath = "./tr/th[contains(text(), 'Playing position')]/ancestor::tr/td/descendant-or-self::a/@href"
    # Get playing position
    position = infobox.xpath(position_xpath)[0].strip().split('#')[0]
    position_ref = get_ontology_entry(position)
    graph.add((player_ref, position_property, position_ref))


def crawl_team_page(team_relative_path):
    team_ref = get_ontology_entry(team_relative_path)
    url = base_path + team_relative_path
    response = requests.get(url)
    doc = lxml.html.fromstring(response.content)
    # Get list of players
    players = doc.xpath("//h2/span[contains(text(), 'Players')]/following::table[1]//tr[contains(@class, 'vcard')]")
    for player in players:
        player_link = player.xpath("./td/span[contains(@class, 'fn')]/a/@href")
        # No player page :(
        if len(player_link) == 0:
            player_name = player.xpath("./td/span[contains(@class, 'fn')]/text()")[0].strip().replace(' ', '_')
            player_ref = get_ontology_entry('/wiki/' + player_name)
            graph.add((player_ref, playsFor_property, team_ref))
        # Else, crawl player page!
        else:
            player_ref = get_ontology_entry(player_link[0])
            graph.add((player_ref, playsFor_property, team_ref))
            crawl_player_page(player_link[0])


def crawl_league_page(league_path):
    response = requests.get(league_path)
    doc = lxml.html.fromstring(response.content)
    # Get league name
    league = doc.xpath("//table[contains(@class, 'infobox')]/caption/a/@href")[0]
    country = get_country_from_league_page(league).strip().replace(' ', '_')
    country_ref = get_ontology_entry('/wiki/' + country)
    league_ref = get_ontology_entry(league)
    graph.add((league_ref, country_property, country_ref))
    # Get list of team rows in table
    rows = doc.xpath("//table[contains(@class, 'sortable')][1][//th[contains(text(), 'Team')]]/tbody/tr")
    for row in rows:
        team = row.xpath("./td[1]/a/@href")
        # No team page/not a team - skip
        if len(team) == 0:
            continue
        team = team[0]
        team_ref = get_ontology_entry(team)
        graph.add((team_ref, league_property, league_ref))
        # Get city from row
        city_link = row.xpath("./td[2]/a/@href")
        # No link to city - generate one
        if len(city_link) == 0:
            city = row.xpath("./td[2]/text()")[0]
            city = city.strip().replace(' ', '_')
            city_ref = get_ontology_entry('/wiki/' + city)
            graph.add((team_ref, homeCity_property, city_ref))
            # Assume city in league's country if no link available
            graph.add((city_ref, located_in_property, country_ref))
        elif city_link[0] == '/wiki/Old_Trafford_(district)':
            # Manchester United insist on being in Old Trafford, which doesn't connect to Manchester in any way
            city = '/wiki/Manchester'
            city_ref = get_ontology_entry(city)
            graph.add((team_ref, homeCity_property, city_ref))
            city_country = get_country_from_city_page(city).strip()
            graph.add((city_ref, located_in_property, get_ontology_entry(city_country)))
        else:
            # Got city and link
            city_ref = get_ontology_entry(city_link[0])
            graph.add((team_ref, homeCity_property, city_ref))
            city_country = get_country_from_city_page(city_link[0]).strip()
            graph.add((city_ref, located_in_property, get_ontology_entry(city_country)))
        # Crawl team page :)
        crawl_team_page(team)
    # Save ontology to file
    graph.serialize('ontology.nt', format='nt')
    return graph


if __name__ == '__main__':
    if len(sys.argv) >= 2:
        url = sys.argv[1]
        crawl_league_page(url)
