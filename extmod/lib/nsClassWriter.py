import struct


import logging
_logger = logging.getLogger("StructWriter")

class StructWriter(object):
    packTypeMap = {int:'i', float:'f', str:'s', bool:'?', bytes:'p'}

    def write(self, obj):
        result = None
        try:
            fields = obj.fields
            if hasattr(obj, 'packstring'):
                packstring = getattr(obj,'packstring')
            else:
                packstring = ''.join(StructWriter.packTypeMap[type(getattr(obj,f))] for f in fields)
            packargs = (getattr(obj,f) for f in fields)
            result = struct.pack(packstring, *packargs)
        except Exception as ex:
            _logger.exc(ex, "Failed to write {nb} bytes using packstring '{s}' - fields = {f}".format(nb=obj.packlength, s=packstring, f=fields))
            pass    
        return result

    def read(self, data, obj):
        fields = obj.fields
        if hasattr(obj, 'packstring'):
            packstring = getattr(obj,'packstring')
        else:
            packstring = ''.join(StructWriter.packTypeMap[type(getattr(obj,f))] for f in fields)
        #packargs = (getattr(obj,f) for f in fields)
        #return struct.pack(packstring, *packargs)
        try:
            t = struct.unpack(packstring,data)
            for idx in range(len(fields)):
                f = fields[idx]
                setattr(obj, f, t[idx])
        except Exception as ex:
            _logger.exc(ex, "Failed to read {nb} bytes '{p}' using packstring '{s}' (required {nb_req} bytes)".format(nb=len(data), p=str(data), s=packstring, nb_req=struct.calcsize(packstring)))
            pass                



class DictWriter(object):
    def write(self, obj):
        return dict((f, getattr(obj,f)) for f in obj.fields)

class JSONWriter(object):
    jsonTypeMap = {str:lambda s:"'"+s+"'"}
    defaultJsonFunc = lambda x:str(x)
    def write(self, obj):
        # not really recommended to roll your own strings, but for illustration...
        fields = obj.fields
        outargs = (getattr(obj,f) for f in fields)
        outvals = (JSONWriter.jsonTypeMap.get(type(arg),JSONWriter.defaultJsonFunc)(arg) 
                       for arg in outargs)
        return ('{' +
            ','.join("'%s':%s" % field_val for field_val in zip(fields, outvals)) +
            '}')

class ZipJSONWriter(JSONWriter):
    def write(self, obj):
        import zlib
        return zlib.compress(super(ZipJSONWriter,self).write(obj))

class HTMLTableWriter(object):
    def write(self, obj):
        out = "<table>"
        for field in obj.fields:
            out += "<tr><td>%s</td><td>%s</td></tr>" % (field, getattr(obj,field))
        out += "</table>"
        return out


