import ifctoneo4j
result = ifctoneo4j.parse('model.ifc')
print(result)
print('nodes:   ', result.node_count)
print('rels:    ', result.rel_count)
print('elements:', result.element_count)

counts = ifctoneo4j.write(
    result,
    neo4j_uri='neo4j+s://9e65deb7.databases.neo4j.io',
    neo4j_user='9e65deb7',
    neo4j_password='Alx9FbDsvrTId0GCF3HSl4oKPsGZ-ZyDxPy2U9TiOkM',
    database='9e65deb7',
    clear_db=True,
)
print(counts)