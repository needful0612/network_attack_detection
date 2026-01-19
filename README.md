0 - 23	Frame Level	Statistics based on the MAC address.	High. Weight (col 0, 5, 10...) is a packet counter.
24 - 47	IP Level	Statistics based on the Source IP.	High. Tracks how active an IP is.
48 - 71	Channel Level	Statistics between specific IP pairs (A to B).	Medium. Good for spotting targeted floods.
72 - 114	Socket Level	Statistics between IP:Port pairs (A:port to B:port).	High (Leakage). This is where Scans/Mirai show up clearly.