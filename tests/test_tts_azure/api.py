import azure.cognitiveservices.speech as speechsdk

def azure_tts_api(data):
    # Use your Azure Cognitive Services subscription key and region
    subscription_key = ""
    service_region = "japanwest"

    # file_name = 'azure_tts_' + self.common.get_bj_time(4) + '.wav'
    # voice_tmp_path = self.common.get_new_audio_path(self.audio_out_path, file_name)
    voice_tmp_path = 'azure_tts_0.wav'
    
    # Create the speech config object using the Azure subscription key and service region
    speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=service_region)
    speech_config.speech_synthesis_voice_name = "zh-CN-liaoning-XiaobeiNeural"

    # Create the audio config object, specifying the output audio file path
    audio_config = speechsdk.audio.AudioOutputConfig(filename=voice_tmp_path)

    # Create the speech synthesizer object
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

    # Perform text-to-speech conversion
    result = speech_synthesizer.speak_text_async(data["content"]).get()

    # Check the result
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print(f"Audio successfully saved to: {voice_tmp_path}")
        return voice_tmp_path
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print(f"Text-to-speech canceled: {str(cancellation_details.reason)}")
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            if cancellation_details.error_details:
                print(f"Error details: {str(cancellation_details.error_details)}")

        return None

# Text to convert
data = {
    "content": "你好"
}


# Call the function
print(azure_tts_api(data))
