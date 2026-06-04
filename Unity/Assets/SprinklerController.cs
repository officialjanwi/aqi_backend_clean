using System.Collections;
using UnityEngine;
using UnityEngine.Networking;

public class SprinklerController : MonoBehaviour
{
    public ParticleSystem waterParticles;   // Drag particle system in Inspector

    string backendUrl = "http://127.0.0.1:8000/live/decision";

    void Start()
    {
        StartCoroutine(CheckBackend());
    }

    IEnumerator CheckBackend()
    {
        while (true)
        {
            // GET request (NO BODY)
            UnityWebRequest request = UnityWebRequest.Get(backendUrl);

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                string response = request.downloadHandler.text;
                Debug.Log("Backend Response: " + response);

                // 🔥 IMPORTANT: backend returns "sprinkler_state":"ON"
                if (response.Contains("\"sprinkler_state\":\"ON\""))
                {
                    waterParticles.Play();
                }
                else
                {
                    waterParticles.Stop();
                }
            }
            else
            {
                Debug.LogError("Error: " + request.error);
            }

            yield return new WaitForSeconds(5f); // check every 5 seconds
        }
    }
}