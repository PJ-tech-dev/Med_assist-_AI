import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        # 1. Login
        login_res = await client.post("http://127.0.0.1:8000/api/v1/auth/login", json={
            "email": "patient@medassist.ai",
            "password": "Password123!"
        })
        print("Login:", login_res.status_code, login_res.text)
        token = login_res.json()["access_token"]
        
        # 2. Get Patients
        headers = {"Authorization": f"Bearer {token}"}
        pat_res = await client.get("http://127.0.0.1:8000/api/v1/patients", headers=headers)
        print("Patients:", pat_res.status_code, pat_res.text)
        patient_id = pat_res.json()["items"][0]["id"]
        
        # 3. Upload
        files = {"file": ("test.txt", b"Test clinical report data here.", "text/plain")}
        data = {"patient_id": patient_id}
        up_res = await client.post("http://127.0.0.1:8000/api/v1/reports/upload", headers=headers, data=data, files=files)
        print("Upload:", up_res.status_code, up_res.text)

asyncio.run(main())
