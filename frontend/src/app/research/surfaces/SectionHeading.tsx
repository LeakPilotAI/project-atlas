export function SectionHeading({id,title,posture}:{id:string;title:string;posture:string}){
 return <div className="mb-3">
  <h2 id={id} className="text-sm font-medium text-zinc-300">{title}</h2>
  <p className="mt-1 text-xs text-zinc-600">{posture}</p>
 </div>
}
