import rdflib


def query():
    graph = rdflib.Graph()
    graph.parse('ontology.nt', format='nt')
    query1 = 'select distinct ?p ?t where { ?p <http://example.org/property/birthPlace> ?c .' \
             '					  	   		?c <http://example.org/property/located_in> <https://en.wikipedia.org/wiki/Netherlands> .' \
             '					  	   		?p <http://example.org/property/playsFor> ?t }'
    res1 = graph.query(query1)
    print(list(res1))
    query2 = 'select distinct ?p ?t where { ?p <http://example.org/property/playsFor> ?t .' \
             '								?p <http://example.org/property/birthDate> ?bd .' \
             '								filter(?bd > "1994-12-31"^^xsd:date) }'
    res2 = graph.query(query2)
    print(list(res2))
    query3 = 'select distinct ?p where { ?p <http://example.org/property/birthPlace> ?c1 .' \
             '					  	     ?p <http://example.org/property/playsFor> ?t .' \
             '							 ?t <http://example.org/property/homeCity> ?c2 .' \
             '							 filter(?c1 = ?c2) }'
    res3 = graph.query(query3)
    print(list(res3))
    query4 = 'select distinct ?t1 ?t2 where { ?t1 <http://example.org/property/league> ?l .' \
             '					  	   		  ?t2 <http://example.org/property/league> ?l .' \
             '					  	   		  ?t1 <http://example.org/property/homeCity> ?c1 .' \
             '								  ?t2 <http://example.org/property/homeCity> ?c2 .' \
             '								  filter(?c1 = ?c2) .' \
             '								  filter(?t1 != ?t2) }'
    res4 = graph.query(query4)
    print(list(res4))


if __name__ == '__main__':
    query()
