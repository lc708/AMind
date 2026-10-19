import json,sys
p=json.load(sys.stdin)
print(json.dumps({'output':p['input'],'cost_usd':.02,'model':'fixture','synthetic':True}))
