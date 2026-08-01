from dataclasses import dataclass
from multiprocessing import Value
from urllib.request import urlopen, Request
from wikitextparser import Template, parse
from json import JSONEncoder, loads, dumps
from typing import Any, Literal, NotRequired, TypedDict, get_args, override
from re import IGNORECASE, findall, sub, match, escape
from pathlib import Path

# TODO is is-dead attr
# TODO: make sure cite verification needed is treated as None

""" LOG FUNCS """
def info(message: Any):
    print(f"[INFO] {message}")

def debug(message: Any):
    print(f"\t[DEBUG] {message}")

def error(message: Any):
    print(f">> ERROR: {message} <<")


""" Classes, types & consts """
ProtocolValue = Literal["yes", "maybe|assigned", "n/a|reserved", "unofficial", "no", "any|compressible"] | None
PROTOCOL_VALUES: list[str] = list(get_args(get_args(ProtocolValue)[0]))
ALL_PROTOCOLS = Literal["tcp", "udp", "sctp", "dccp"]

REGEX_PORTS = r"(?P<ports>[0-9-]+)"
REGEX_INLINE_REF = r"(?<=<ref )[^/>]*?(?=/>)"
REGEX_PROTOCOL = r"(|\W*?colspan=(\"|)(?P<colspan>[1-4])(\"|)\W*?){{(?P<value>(" + "|".join([escape(value.lower()) for value in PROTOCOL_VALUES]) + r"))}}"
REGEX_FIND_ENTRIES = r"[^\w]"  # Only keep alphanumeric for stabler search. hopefully

class Citation(TypedDict):
    url: str
    access_date: NotRequired[str]

# Return arg of key from wikitext template. See Entry.add_citation
def get_from_template(template: Template, key: str) -> str|None:
    val = template.get_arg(key)
    if val and val.value:
        return val.value
    else:
        return None

class Entry():
    citation_urls: list[Citation]

    ports: str|None = None

    tcp: ProtocolValue = None
    udp: ProtocolValue = None
    sctp: ProtocolValue = None
    dccp: ProtocolValue = None

    description: str|None = None

    protocols_set: int = 0  # See add_protocol

    def __init__(self):
        self.citation_urls = []

    @override
    def __str__(self):
        return f"port: {self.ports} | tcp: {self.tcp} | udp: {self.udp} | sctp: {self.sctp} | dccp: {self.dccp} | description: {self.description} | citation_urls: {','.join(list(map(lambda cite: cite["url"], self.citation_urls)))}"

    def get_protocol(self, key: ALL_PROTOCOLS):
        # TODO: cleaner
        match key:
            case "tcp":
                return self.tcp
            case "udp":
                return self.udp
            case "sctp":
                return self.sctp
            case "dccp":
                return self.dccp


    """
    The protocol values are passed in the table by either a template or an empty cell
    these cells, however, can have a colspan.
    The empty cells together with the colspan always add up to 4 in total

    The code in __main__ handles:
    - Passing protocol value columns content to add_protocol
    - Adding the port multiple times depending on colspan
    
    This function is rather "dumb" in some regards:
    - Keep track of how many protocols have been assigned
        - If none, set to tcp
        - If one, set to udp
        - ...
    - If passed a correct ProtocolValue, set it to the next protocol
    - If passed "", skip protocol
    """
    def add_protocol(self, value: str):
        if value == "":  # Leave protocol at None & skip
            self.protocols_set += 1
            return

        value = value.lower()  # Wiki templates are not consistently cased
        if value not in PROTOCOL_VALUES:  # But it must be a valid ProtocolValue
            raise ValueError(f"{value} is not in {PROTOCOL_VALUES}")
        
        protocols_set = self.protocols_set
        match protocols_set:  # Set value to next protocol
            case 0:
                debug(f"Setting tcp to {value}")
                self.tcp = value
            case 1:
                debug(f"Setting udp to {value}")
                self.udp = value
            case 2:
                debug(f"Setting sctp to {value}")
                self.sctp = value
            case 3:
                debug(f"Setting dccp to {value}")
                self.dccp = value
            case _:
                raise IndexError("No more protocols left to set!")

        self.protocols_set += 1  # Move index to the next protocol

    def add_citation(self, colValue: str):
        assert type(colValue) == str  # Type safety
        templates = parse(colValue).templates  # Parse wikitext, get templates

        # From self-closing <ref/> (e.g. no content)
        inline_ref = findall(REGEX_INLINE_REF, colValue)
        for ref in inline_ref:
            self.citation_urls.append({
                "url": f"Inline reference: {ref}"
            })

        # From {{ Cite }}
        if templates and len(templates) == 2:
            for template in templates:
                # Only consider cite templates. Remember that templates aren't case sensitive, but python is
                if template.name.lower().startswith("cite "):
                    # Get access date if its there
                    access_date = get_from_template(template, "access-date")

                    form = ""  # Format for the url, if a specific cite is used
                    # Get template names of this template usage
                    template_names = list(filter(lambda x: x is not "", template.name.split(" ")))
                    if len(template_names) == 2:  # For example: {{cite ietf}}
                        form = template_names[1]  # For example: ietf
                    elif len(template_names) > 2:
                        raise ValueError("Too many template names")
                    
                    if form == "IETF":  # Has two versions: rfc & draft
                        rfc = get_from_template(template, "rfc")
                        draft = get_from_template(template, "draft")

                        if rfc:
                            url = f"https://www.rfc-editor.org/info/rfc{rfc}"
                        elif draft:
                            url = f"https://datatracker.ietf.org/doc/html/opsawg-tacacs-10"
                        else:
                            raise ValueError("no url found for ietf")

                    elif form == "conference":
                        url = "N/A (conference)"
                    else:
                        url = get_from_template(template, "url")

                    # No matter what format, url must be defined and a string
                    assert type(url) == str  

                    citation: Citation = {"url": url}
                    if access_date:
                        citation["access_date"] = access_date
                    self.citation_urls.append(citation)

    def is_cited(self):
        return bool(len(self.citation_urls) >= 1)

class EntryEncoder(JSONEncoder):
    @override
    def default(self, o):

        if isinstance(o, Entry):
            return {
                "ports": o.ports,
                "description": o.description,
                "tcp": o.tcp,
                "udp": o.udp,
                "sctp": o.sctp,
                "dccp": o.dccp,
                "citation_urls": o.citation_urls,
            }
        return super().default(o)

def loweralphanumeric(string: str):
    return sub(REGEX_FIND_ENTRIES, "", string).lower()

def find_entries(entries: list[Entry], key: str):
    out: list[Entry] = []
    key = loweralphanumeric(key)
    for entry in entries:
        if key in loweralphanumeric(entry.description):
            out.append(entry)
    return out

""" Testing """
class SanityTest(TypedDict):
    search_key: str
    ports: str
    tcp: NotRequired[ProtocolValue]
    udp: NotRequired[ProtocolValue]
    sctp: NotRequired[ProtocolValue]
    dccp: NotRequired[ProtocolValue]
    index: NotRequired[int]

def assert_and_log(key: str, output_value: Any, expected_value: Any):
    debug(f"Entry {key} {output_value} == expected {expected_value}?")
    assert output_value == expected_value
    debug("Success!")
 


if __name__ == "__main__":
    tests: list[SanityTest] = [
        {
            "search_key": "id softwares quakeworld",
            "index": 0,
            "ports": "27000-27006",
            "udp": "unofficial"
        },
        {
            "search_key": "QuakEwoRld",
            "index": 1,
            "ports": "27500-27900",
            "udp": "unofficial"
        },
        {
            "search_key": "Factorio",
            "ports": "34197",
            "tcp": "no",
            "udp": "unofficial"
        }
    ]
    # Step 1: determine user agent, as by wikipedia policy
    user_agent_path = Path(".user-agent")
    if not user_agent_path.exists():
        user_agent = input("Insert User-Agent according to 'https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy':")
        _ = user_agent_path.write_text(user_agent, "utf-8")
    else:
        user_agent = user_agent_path.read_text(encoding="utf-8") 

    info("Using User-Agent: " + user_agent)


    debug("Using following protocol regex: " + REGEX_PROTOCOL)


    # Step 2: Get latest page version from Wikipedia & cleanup for better parsing
    try:
        req = Request("https://en.wikipedia.org/w/rest.php/v1/page/List_of_TCP_and_UDP_port_numbers")
        req.add_header("User-Agent", user_agent)
        with urlopen(req) as resp:
            source: str = loads(resp.read().decode("utf-8")).get("source")
            
            source = sub(r"<!--.*?-->", "", source).replace("\u2013", "-")
    except Exception as e:
        raise e


    # Step 3: Parse the tables in the article
    parsed = parse(source)
    out: list[Entry] = []

    port_sections = [
        parsed.sections[2],  # well_known_ports 
        parsed.sections[3],  # registered_ports
        parsed.sections[4]   # dynamic_private_ephemeral_ports
    ]
    for section in port_sections:
        # Sanity check: 1 table expected per section
        assert len(section.tables) == 1  
        table = section.tables[0]

       

        rows = table.data()  # list[list[str]]: [[cell, cell, cell], [cell, cell, cell, cell]]
        del rows[0]  # Header row

        for cols in rows:
            # Filter out non-existant cells, usually at the end
            cols = list(filter(lambda cell: cell != None, cols))
            
            entry = Entry()

            for col in cols:
                if col:
                    entry.add_citation(col)  # Get any refs from columns field

            entry.ports = cols[0]
            del cols[0]  # Remove ports from cells to allow cleaner iteration

            info(f"Handling data for ports: {entry.ports}")

            i = 0
            while i != len(cols):
                col = cols[i]
                assert type(col) == str  # Make sure not none

                # If an empty cell, notify the class that a None value is due and go to next cell
                if col == "":
                    entry.add_protocol("")
                    i += 1
                    continue


                # Colspan wasn't fetchable using wikitextparser: use regex
                protocol = match(REGEX_PROTOCOL, col, IGNORECASE)
                if protocol == None:
                    debug("No protocol found, continuing")
                    break

                colspan = protocol.group("colspan")
                if not colspan:
                    add = [ 1 ]
                else:
                    add = range(0, int(colspan))

                for j in add:  # Add port for ever column spanned
                    protocol_value = protocol.group("value")
                    entry.add_protocol(protocol_value)

                i+=1

            # At least one needs a value
            assert bool(entry.tcp or entry.udp or entry.sctp or entry.dccp)

            # By now, we need to have hit description. It should be the last column
            assert i == len(cols) - 1 and cols[i]  
            entry.description = cols[i]

            debug(entry)

            out.append(entry)  

    for test in tests:
        debug(f"Test: {test}")

        found_entry = find_entries(out, test["search_key"])[test.get("index", 0)]

        assert_and_log(
            "ports",
            output_value=found_entry.ports,
            expected_value=test["ports"])

        for protocol in get_args(ALL_PROTOCOLS):
            assert_and_log(
                "protocol",
                output_value=found_entry.get_protocol(protocol),
                expected_value= test.get(protocol, None)  # None is default value, aka unset
            )
           
    _ = Path("list.json").write_text(dumps(out, cls=EntryEncoder, indent=2), encoding="utf-8")



   


        

