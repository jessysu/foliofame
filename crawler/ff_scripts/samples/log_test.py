from pymongo import MongoClient
client = MongoClient('mongodb://%s:%s@mongodb:27017' % ("root", "test"))
db = client['mongotest']
posts = db.posts
post_data = {
    'title': 'Python and MongoDB',
    'content': 'PyMongo is fun, you guys',
    'author': 'Scott'
}
result = posts.insert_one(post_data)
print('One post: {0}'.format(result.inserted_id))
