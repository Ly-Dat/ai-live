from gradio_client import Client
import traceback, logging

client = Client("http://127.0.0.1:7860/")


def get_local_knowledge_base_list():
    """Get the current list of knowledge bases

    Returns:
        list: Knowledge base list
    """
    result = client.predict(
                    fn_index=1
    )
    try:
        list = result[0]["choices"]
        print(f'Local knowledge base list:{list}')
        return list
    except Exception as e:
        print(traceback.format_exc())
        return None
    



