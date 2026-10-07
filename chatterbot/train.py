from chatterbot import ChatBot
from chatterbot.trainers import ListTrainer

# Read the corpus file
with open('data/db.txt', 'r', encoding='utf-8') as f:
    corpus = f.readlines()

# Create a ChatBot instance and train it
my_bot = ChatBot(input('Enter the ChatBot name: '))
trainer = ListTrainer(my_bot)
print('Training started!')
trainer.train(corpus)
print('Training finished!')
