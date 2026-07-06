from app.integrations.ip.ip_service import IpAnalysisService

text = """
IP interno: 192.168.15.2
IP público: 177.12.176.38
IPv6: 2804:1b3:7140:e013:2d1b:9175:ad57:932e
Loopback: 127.0.0.1
"""

service = IpAnalysisService()
results = service.analyze_text(text)

for result in results:
    print(result.ip)
    print(result.severity)
    print(result.lookup_performed)
    print(result.location_summary)
    print(result.technical_summary)
    print(result.message)
    print("-" * 40)