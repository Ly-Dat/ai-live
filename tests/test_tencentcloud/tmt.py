import json
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.tmt.v20180321 import tmt_client, models
try:
    # Instantiate a credential object with the Tencent Cloud SecretId and SecretKey; keep the key pair secret
    # A code leak may expose SecretId and SecretKey and threaten every resource under the account. The sample below is for reference only; use a safer way to handle keys, see:https://cloud.tencent.com/document/product/1278/85305
    # Keys can be obtained from the console at https://console.cloud.tencent.com/cam/capi
    cred = credential.Credential("SecretId", "SecretKey")
    # Instantiate an http option (optional, can be skipped)
    httpProfile = HttpProfile()
    httpProfile.endpoint = "tmt.ap-shanghai.tencentcloudapi.com"

    # Instantiate a client option (optional, can be skipped)
    clientProfile = ClientProfile()
    clientProfile.httpProfile = httpProfile
    # Instantiate the client object for the product; clientProfile is optional
    client = tmt_client.TmtClient(cred, "ap-shanghai", clientProfile)

    # Instantiate a request object; each API has its own request object
    req = models.TextTranslateRequest()
    params = {
        "SourceText": "test",
        "Source": "auto",
        "Target": "zh",
        "ProjectId": 0
    }
    req.from_json_string(json.dumps(params))

    # The returned resp is a TextTranslateResponse instance matching the request object
    resp = client.TextTranslate(req)
    # Output the JSON string response
    print(resp.to_json_string())

except TencentCloudSDKException as err:
    print(err)