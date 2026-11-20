export function AuthorityLegendItem({term,meaning}:{term:string;meaning:string}){
 return <div className="rounded-lg border border-white/5 p-3"><dt className="font-medium text-zinc-300">{term}</dt><dd className="mt-1 leading-5 text-zinc-500">{meaning}</dd></div>
}

export function ActiveEvidenceState({label,value}:{label:string;value:string}){
 return <div className="rounded-lg border border-white/5 px-3 py-3"><p className="text-zinc-500">{label}</p><p className="mt-1 text-zinc-300">{value}</p></div>
}
