from urllib.request import urlopen, Request
from wikitextparser import Template, parse
from json import loads
from typing import Literal, NotRequired, TypedDict, get_args, override
from re import IGNORECASE, findall, sub, match, escape
from pathlib import Path

ProtocolValue = Literal["yes", "maybe|assigned", "n/a|reserved", "unofficial", "no", "any|compressible"] | None
protocol_values: list[str] = list(get_args(get_args(ProtocolValue)[0]))

user_agent_path = Path(".user-agent")
if not user_agent_path.exists():
    user_agent = input("Insert User-Agent according to https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy: ")
    _ = user_agent_path.write_text(user_agent, "utf-8")
else:
    user_agent = user_agent_path.read_text(encoding="utf-8") 

print(f"User-Agent: " + user_agent)

class Citation(TypedDict):
    url: str
    access_date: NotRequired[str]


class Entry():
    citation_urls: list[Citation] = []

    ports: str|None = None

    tcp: ProtocolValue = None
    udp: ProtocolValue = None
    sctp: ProtocolValue = None
    dccp: ProtocolValue = None

    protocols_set: int = 0

    description: str|None = None
    
    @override
    def __str__(self):
        return f"port: {self.ports} | tcp: {self.tcp} | udp: {self.udp} | sctp: {self.sctp} | dccp: {self.dccp} | description: {self.description}"

    def add_protocol(self, value: str):
        value = value.lower()
        if value not in protocol_values:
            raise ValueError(f"{value} is not in {protocol_values}")
        
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

        self.protocols_set += 1

    def add_citation(self, rawValue: str):
        assert type(rawValue) == str
        templates = parse(rawValue).templates

        if templates and len(templates) == 2:
            for template in templates:
                if template.name.lower().startswith("cite "):
                    print(template)
                    def get_from_template(template: Template, key: str) -> str|None:
                        val = template.get_arg(key)
                        if val and val.value:
                            return val.value
                        else:
                            return None

                    access_date = get_from_template(template, "access-date")

                    form = ""
                    template_names = list(filter(lambda x: x is not "", template.name.split(" ")))
                    print(template_names)
                    if len(template_names) == 2:
                        form = template_names[1]
                    elif len(template_names) > 2:
                        raise ValueError("Too many template names")

                    
                    if form == "IETF":
                        rfc = get_from_template(template, "rfc")
                        draft = get_from_template(template, "draft")

                        if rfc:
                            url = f"https://www.rfc-editor.org/info/rfc{rfc}"
                        elif draft:
                            url = f"https://datatracker.ietf.org/doc/html/opsawg-tacacs-10"  # TODO is is-dead attr
                        else:
                            raise ValueError("no url found for ietf")

                        print(url)
                    elif form == "conference":
                        url = "N/A (conference)"
                    else:
                        url = get_from_template(template, "url")

                    assert url is not None

                    out: Citation = {"url": url}
                    if access_date:
                        out["access_date"] = access_date
                    self.citation_urls.append(out)
                    


        print("raw " + rawValue)

        refs = match(r"{{cite(?P<content>([^}]|\n)+?)}}", rawValue, IGNORECASE)
        print("Found citations:")
        print(refs)
        if not refs:
            return
        for ref in refs:
            print(ref)
            print(parse(ref))
            print("MEow")
            exit()
        

    def is_cited(self):
        return bool(len(self.citation_urls) >= 1)


REGEX_PORTS = r"(?P<ports>[0-9-]+)"
REGEX_PROTOCOL = r"(|\W*?colspan=(\"|)(?P<colspan>[1-4])(\"|)\W*?){{(?P<value>(" + "|".join([escape(value.lower()) for value in protocol_values]) + r"))}}"
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
            cells = list(filter(lambda cell: cell != None, cells))
            # print(f"Parsing {cells}")

            entry = Entry()

            entry.ports = cells[0]
            del cells[0]

            print(f"Handling data for ports: {entry.ports}")
            print(cells)


            i = 0
            while i != len(cells):
                cell = cells[i]
                assert type(cell) == str  # Make sure not none

                if cell == "":  # Empty protocol aka none
                    i += 1
                    continue

                entry.add_citation(cell)


                protocol = match(REGEX_PROTOCOL, cell, IGNORECASE)
                # cell = parse(cell)
                #
                # print(cell.attrs)
                #
                # templates = cell.templates
                # protocol = templates[0].name.lower()
                # assert protocol in protocol_values
                # if len(templates) > 1:
                #     for j in range(1, len(templates)):
                #         print(templates[j].arguments[0])


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
            # At least one needs a value
            assert bool(entry.tcp or entry.udp or entry.sctp or entry.dccp)

            assert i == len(cells) - 1 and cells[i]  # Description should be last

            entry.description = cells[i]
            entry.add_citation(entry.description)

            print(entry)


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
