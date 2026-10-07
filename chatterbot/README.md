## Runtime Environment
- Python 3.6+

## Install Dependencies
Install the required libraries with the following command:
```bash
pip install spacy ChatterBot
```

If installing ChatterBot fails, go to https://github.com/RaSan147/ChatterBot_update and install the newer version. Download it and run `python setup.py install`.  
If installation is slow, install it separately: `pip install SQLAlchemy==1.3.24`  

## How to Train Your Own AI
- Open `data/db.txt` and write the content you want to train on, in the following format:
```
Question
Answer
Question
Answer
```
- Rename the file to `data/db.txt`
- Run the following command in a terminal to start the program:
```bash
python train.py
```
- The trained model is named `db.sqlite3`; just double-click `main.py` to use it.

## FAQ
1. If it reports that en-core-web-sm is missing, open a terminal and run:
```bash
python -m spacy download en_core_web_sm
```
2. Error "no module named 'spacy'": how to fix
```bash
pip install spacy
```

## License
MIT License. See the LICENSE file for details.

## Additional Notes

### ChatterBot
ChatterBot is an open-source Python chatbot framework that uses machine learning algorithms (especially natural language processing and text semantic analysis) to build rule- and context-based automatic chat systems. With simple configuration and training, developers can build many kinds of chatbots, including Q&A bots, task-oriented bots, and casual chat bots.

The core idea of ChatterBot is to use machine learning and natural language processing to analyze and predict user input based on historical conversation data, and then generate a response. With this approach, the chatbot responds more intelligently, flexibly, and in a way closer to human conversation. In addition, ChatterBot supports multiple storage backends such as JSON, SQLAlchemy, and MongoDB, and multiple interfaces such as RESTful API and WebSocket, making it easy for developers to integrate in different scenarios.

Overall, ChatterBot is a powerful, flexible, and easy-to-use chatbot framework that helps developers quickly build personalized, customized chatbots, improving user experience and service quality.