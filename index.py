from urllib.request import urlopen, Request
from webbrowser import get
from wikitextparser import parse
from json import loads
from typing import Literal, get_args
from re import sub, match, escape
from pathlib import Path

ProtocolValue = Literal["yes", "Maybe|Assigned", "N/A|Reserved", "unofficial", "no"] | None
protocol_values: list[str] = list(get_args(get_args(ProtocolValue)[0]))

user_agent_path = Path(".user-agent")
if not user_agent_path.exists():
    user_agent = input("Insert User-Agent according to https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy: ")
    _ = user_agent_path.write_text(user_agent, "utf-8")
else:
    user_agent = user_agent_path.read_text(encoding="utf-5") 
    

with open(".user-agent", "r", encoding="utf-8"):
    pass

class Entry():
    citation_urls: list[str] = []

    ports: str|None = None

    tcp: ProtocolValue = None
    udp: ProtocolValue = None
    sctp: ProtocolValue = None
    dccp: ProtocolValue = None

    protocols_set = 0

    def __init__(self):
        self.description: str = ""

    def __str__(self):
        return f"port: {self.ports} | tcp: {self.tcp} | udp: {self.udp} | sctp: {self.sctp} | dccp: {self.dccp} | citation_urls: {', '.join(self.citation_urls)}"

    def set_protocol(self, keyIndex: int, value: str):
        pass

    def add_protocol(self, value: str):
        if value not in protocol_values:
            raise ValueError(f"${value} is not in ${protocol_values}")
        
        protocols_set = self.protocols_set
        match protocols_set:
            case 0:
                print(f"Setting tcp to {value}")
                self.tcp = value
            case 1:
                print(f"Setting udp to {value}")
                self.udp = value
            case 2:
                print(f"Setting sctp to {value}")
                self.sctp = value
            case 3:
                print(f"Setting dccp to {value}")
                self.dccp = value
            case _:
                raise IndexError("No more protocols left to set!")


                print(protocol)
        self.protocols_set += 1
        
        

    def is_cited(self):
        return bool(len(self.citation_urls) >= 1)


REGEX_PORTS = r"(?P<ports>[0-9-]+)"
REGEX_PROTOCOL = r"(\W*?colspan=(?P<colspan>[1-4])\W*){{(?P<value>(" + "|".join([escape(value) for value in protocol_values]) + r"))}}"
print(REGEX_PROTOCOL)

if __name__ == "__main__":
    # Step 1: Read from
    try:
        req = Request("https://en.wikipedia.org/w/rest.php/v1/page/List_of_TCP_and_UDP_port_numbers")
        req.add_header("User-Agent", user_agent)
        with urlopen(req) as resp:
            source: str = loads(resp.read().decode("utf-8")).get("source")
            
            source = sub(r"<!--.*?-->", "", source)
    except Exception as e:
        raise e

    parsed = parse(source)

    port_sections = [
        parsed.sections[2],  # well_known_ports 
        parsed.sections[3],  # registered_ports
        parsed.sections[4]   # dynamic_private_ephemeral_ports
    ]
    for section in port_sections:
        assert len(section.tables) == 1

        table = section.tables[0]

        rows = table.data()  # [[cell, cell, cell], [cell, cell, cell, cell]]
        del rows[0]  # Header

        # print(table)
        for cells in rows:
            print(f"Parsing {cells}")

            entry = Entry()

            entry.ports = cells[0]
            del cells[0]

            i = 0
            while i != len(cells):
                cell = cells[i]
                assert type(cell) == str  # Make sure not none

                protocol = match(REGEX_PROTOCOL, cell)

                if protocol == None:
                    print("No protocol found, continuing")
                    break
                
                colspan = protocol.group("colspan")
                if not colspan:
                    add = [ 1 ]
                else:
                    add = range(0, int(colspan))

                for j in add:
                    protocol_value = protocol.group("value")
                    entry.add_protocol(protocol_value)

                i+=1

            print(entry)


            # Double wrap get_args, as the type is Literal|None
            print("Yes" in get_args(get_args(ProtocolValue)[0]))
            exit()
            entry.ports = cells[0]
            if cells[0] != "9":
                continue

            print(cells[1])

            
            
        print("---")



        # exit()
        continue

        

        cells = str(section.get_tables(True)[0]).split("|-")
        #for i in range(0, len(rows), 3):
        del cells[0]  # Skip table title
        del cells[0]  # Skip header cells
        for cells in cells:
            # row = rows[i]
            
            cols = cells.split("||")
            from re import sub, MULTILINE
            cols = list(map(lambda col: sub("|", col, "m").strip(), cols))
            print(f"Parsing cols {cols}")
            from re import match

            # Expect empty
            for index in [2, 0]:
                print(f"'{len(cols[index])}'")
                assert len(cols[index]) == 0
                del cols[index]


            print("Parsing port from " + cols[0])
            ports = match(REGEX_PORTS, cols[0])
            assert ports  # Make sure its not none

            ports = ports.group("ports")
            print(ports)
            #
            
            for col in cols:
                col = col.strip()
                
                print(col)

        # print(table)
        # exit()
    




    exit()

    for section in parsed.tables:

        cells = section.data()

        for cells in cells:
            print(cells)
