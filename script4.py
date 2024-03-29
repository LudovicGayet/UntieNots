########################################
#
#	SCRIPT 4
#
########################################
#* Open the exported parquet files.
#* For each topic find :
#- the sources associated with the number of occurrences for each key word.
#- the false positives (sources identified with the keywords that do not belong to the topic) => We assume that a source belongs to a topic if X% of its keywords can be found in the source. (X is an argument of the script).
#- the relevance of each keyword: rate of presence in a source belonging to the topic/ rate of presence in a topic not belonging to the topic / rate of absence in a topic that belonged to the topic
########################################

# Gestion des packages
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import json

# Gestion de l'argument X
# default X = 0.2
import argparse

def restricted_float(x):
    try:
        x = float(x)
    except ValueError:
        raise argparse.ArgumentTypeError("%r not a floating-point literal" % (x,))

    if x < 0.0 or x > 1.0:
        raise argparse.ArgumentTypeError("%r not in range [0.0, 1.0]"%(x,))
    return x

p = argparse.ArgumentParser()
parser = argparse.ArgumentParser(description='Enter a float X: 0<X<1 ex: 0.2')
parser.add_argument('integers', metavar='X', type=restricted_float, default=0.2, nargs='?',
                   help='an integer for the false positive indicator')

args = parser.parse_args()

#####################################################################################################################
# Read file from queue2 and create clean dataset with json (column value) parsed
# dataframe FORMAT :
#         key                                              value                     source      word   topics
#0     sport  {"source": "bbc-dataset/sport/061.txt", "word"...  bbc-dataset/sport/061.txt     title  [sport]
#1     sport  {"source": "bbc-dataset/sport/060.txt", "word"...  bbc-dataset/sport/060.txt     title  [sport]
#2     sport  {"source": "bbc-dataset/sport/061.txt", "word"...  bbc-dataset/sport/061.txt   olympic  [sport]
#3     sport  {"source": "bbc-dataset/sport/060.txt", "word"...  bbc-dataset/sport/060.txt     title  [sport]
#####################################################################################################################

queue2 = pq.read_table('./queue2/part-00000-46e0f89a-b658-4043-b5f3-f019f5b137b0-c000.snappy.parquet')
df = queue2.to_pydict()
df = pd.DataFrame.from_dict(df)
df["source"]=df.value.apply(lambda x:json.loads(x)["source"])
df["word"]=df.value.apply(lambda x:json.loads(x)["word"])
df["topics"]=df.value.apply(lambda x:json.loads(x)["topics"])

#####################################################################################################################
#	For each topic find :
# - the sources associated with the number of occurrences for each key word.
#####################################################################################################################

topic_list = {"sport": ['doping', 'olympic', 'injury','medal','record','title','world','athletic'], \
			"tech" : ['technology','author','article','computer','hi-tech','software','network','security','phone']}

# Creation des sources associées pour chaque topic
df["topics_str"] = df.topics.apply(lambda x : " ".join(x)) 
topic_sport_source = list(set(df[df.topics_str.str.contains("sport")]["source"].tolist()))
print("Source du topic sport: ",topic_sport_source)
topic_tech_source = list(set(df[df.topics_str.str.contains("tech")]["source"].tolist()))
print("Source du topic tech: ",topic_tech_source)

# Calcul du nombre d'occurences des mots clés du topic sport
topic_sport_list_keyword = list(df[df.topics_str.str.contains("sport")]["word"].tolist())
topic_sport_list_keyword = [x for x in topic_sport_list_keyword if x in topic_list["sport"]]
topic_sport_nb_occurence_keyword = {}
for i in topic_list["sport"]:
	topic_sport_nb_occurence_keyword[i]=topic_sport_list_keyword.count(i)

print("Topic sport et nombre d'occurences de chaque keyword: ", topic_sport_nb_occurence_keyword)

# Calcul du nombre d'occurences des mots clés du topic tech
topic_tech_list_keyword = list(df[df.topics_str.str.contains("tech")]["word"].tolist())
topic_tech_list_keyword = [x for x in topic_tech_list_keyword if x in topic_list["tech"]]
topic_tech_nb_occurence_keyword = {}
for i in topic_list["tech"]:
	topic_tech_nb_occurence_keyword[i]=topic_tech_list_keyword.count(i)

print("Topic tech et nombre d'occurences de chaque keyword: ", topic_tech_nb_occurence_keyword)

#####################################################################################################################
#	For each topic find :
# - the false positives (sources identified with the keywords that do not belong to the topic) 
# 	=> We assume that a source belongs to a topic if X% of its keywords can be found in the source. (X is an argument of the script).
#####################################################################################################################

# default X = 0.2
X=args.integers

def topic_deducted_from_keyword(list_keyword, topic_list):
# A partir d'une liste de keyword, défini si une source appartient à un ou plusieurs topics
	topic_deducted = []
	for topic in topic_list:
		if (len(set(list_keyword) & set(topic_list[topic]))/len(topic_list[topic]))>X:
			topic_deducted.append(topic)
	return topic_deducted

df_for_false_positive = df.groupby('source')

list_false_positive = []
for name, group in df_for_false_positive:
	real_topic = set(group["key"].tolist())
	list_keyword=set(group["word"].tolist())
	list_topic_deduit=topic_deducted_from_keyword(list_keyword,topic_list)
	if not set(list_topic_deduit).issubset(real_topic):
		list_false_positive.append(name)
		# Pour comprendre la liste des faux positifs
		#print("source: ",name,"	vrai topic: ",set(group["key"]),"	topic déduit: ",list_topic_deduit,"		et keyword associé: ",list_keyword)

print("liste des faux positifs: ",list_false_positive)

#####################################################################################################################
#	For each topic find :
# - the relevance of each keyword: 
# rate of  : (presence in a source belonging to the topic) / (presence in general)
#####################################################################################################################


def rate_of_presence_in_good_source(real_topic,list_number_occurence_keyword_per_topic):
# calcul pour un mot clé : (presence in a source belonging to the topic) / (presence in general)
	total_of_source = 0
	good_source = 0
	if len(list_number_occurence_keyword_per_topic)==0:
		return 0
	for topic in list_number_occurence_keyword_per_topic:
		if topic==real_topic:
			good_source=good_source+list_number_occurence_keyword_per_topic[topic]
			total_of_source=total_of_source+list_number_occurence_keyword_per_topic[topic]
		else:
			total_of_source=total_of_source+list_number_occurence_keyword_per_topic[topic]
	return good_source/total_of_source

for topic in topic_list:
	for keyword in topic_list[topic]:
		temp_df = df[df.word.str.contains(keyword)]
		temp_df = temp_df.drop_duplicates("source")
		temp_df = temp_df.groupby('key').count()
		# Pour voir le tableau des occurences du keyword par topic
		#print(temp_df)
		list_number_occurence_keyword_per_topic = {}
		for index, row in temp_df.iterrows():
			list_number_occurence_keyword_per_topic[index]=row['value']
		print("Keyword :",keyword,"		rate of presence in good source: ",rate_of_presence_in_good_source(topic,list_number_occurence_keyword_per_topic))


		
