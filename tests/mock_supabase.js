// Browser UI contract fixture only. Database authorization is tested separately.
let listener;
let user = null;
let entries = [
  {id:'00000000-0000-0000-0000-000000000011',term:'own term',meaning:'自己的词',pos:'noun',domains:['医学'],tags:[],example:'',source:'',source_url:'',owner_id:'alice',author_name:'Alice',provenance:'',revision:1},
  {id:'00000000-0000-0000-0000-000000000012',term:'other term',meaning:'其他人的词',pos:'noun',domains:[],tags:[],example:'<img src=x onerror=window.injected=true>',source:'source',source_url:'javascript:alert(1)',owner_id:'bob',author_name:'Bob',provenance:'',revision:1},
];
window.mockCalls = [];
window.mockConflict = false;
window.mockSignIn = (id) => { user = {id,user_metadata:{user_name:id}}; listener?.('SIGNED_IN',{user}); };
window.mockRefresh = () => listener?.('TOKEN_REFRESHED',{user});
export function createClient() {
  return {
    auth: {
      onAuthStateChange(callback) { listener = callback; },
      async getSession() { return {data:{session:user ? {user} : null}}; },
      async signOut() { user=null; listener('SIGNED_OUT',null); return {}; },
      async signInWithOAuth(options) { window.mockCalls.push(['oauth',options]); return {}; },
    },
    async rpc(name) { return {data:name === 'is_admin' && user?.id === 'admin'}; },
    from() {
      let operation = 'read', payload, after = null;
      const conditions = [];
      const query = {
        select() { return query; }, order() { return query; }, limit() { return query; },
        gt(_key,value) { after=value; return query; },
        eq(key,value) { conditions.push([key,value]); return query; },
        insert(value) { operation='insert'; payload=value; return query; },
        update(value) { operation='update'; payload=value; return query; },
        delete() { operation='delete'; return query; },
        then(resolve) {
          window.mockCalls.push([operation,payload,conditions]);
          if (operation === 'read') return Promise.resolve({data:entries.filter(e => !after || e.id > after).sort((a,b)=>a.id.localeCompare(b.id)).slice(0,1)}).then(resolve);
          if (window.mockConflict) return Promise.resolve({data:[]}).then(resolve);
          if (operation === 'insert') {
            entries.push({...payload,id:'00000000-0000-0000-0000-000000000013',revision:1,provenance:''});
            return Promise.resolve({data:[]}).then(resolve);
          }
          const matched = entries.filter(e=>conditions.every(([key,value])=>e[key] === value));
          if (operation === 'update') matched.forEach(e=>{Object.assign(e,payload);e.revision++;});
          if (operation === 'delete') entries=entries.filter(e=>!matched.includes(e));
          return Promise.resolve({data:matched}).then(resolve);
        },
      };
      return query;
    },
  };
}
