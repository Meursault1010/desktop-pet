// A deliberately small Markdown reader for chat answers: headings, lists, fenced code,
// bold, inline code and links. No HTML is ever produced from the text itself, so a model
// answer cannot inject markup; links are only clickable when they are http(s).
export type Inline={text:string;bold?:boolean;code?:boolean;link?:string};
export type Block=
  |{kind:'paragraph';inlines:Inline[]}
  |{kind:'heading';level:number;inlines:Inline[]}
  |{kind:'list';ordered:boolean;items:Inline[][]}
  |{kind:'code';lang:string;lines:string[]};

const FENCE=/^\s*```(.*)$/,HEADING=/^(#{1,3})\s+(.*)$/,BULLET=/^\s*[-*]\s+(.*)$/,ORDERED=/^\s*\d+[.)]\s+(.*)$/;
const TOKEN=/(\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\))/;

export function safeLink(value:string){
  const url=String(value||'').trim();
  return /^https?:\/\/\S+$/i.test(url)&&!/^https?:\/\/\S*@/i.test(url)?url:'';
}

export function inlineTokens(text:string):Inline[]{
  let rest=String(text||'');const out:Inline[]=[];
  while(rest.length){
    const match=rest.match(TOKEN);
    if(!match||match.index===undefined){out.push({text:rest});break;}
    if(match.index>0)out.push({text:rest.slice(0,match.index)});
    const [,whole,bold,code,label,href]=match;
    if(bold)out.push({text:bold,bold:true});
    else if(code)out.push({text:code,code:true});
    else{
      const url=safeLink(href||'');
      out.push(url?{text:label||url,link:url}:{text:whole});
    }
    rest=rest.slice(match.index+whole.length);
  }
  return out;
}

export function parseMarkdown(input:string):Block[]{
  const blocks:Block[]=[];
  const lines=String(input||'').replace(/\r\n?/g,'\n').split('\n');
  let code:string[]|null=null,codeLang='',list:Inline[][]|null=null,listOrdered=false,paragraph:string[]=[];
  // Continuation lines keep their line breaks: chat turns render paragraphs with pre-wrap, so
  // a message typed with Shift+Enter still reads the way the user wrote it.
  const flushParagraph=()=>{if(paragraph.length){blocks.push({kind:'paragraph',inlines:inlineTokens(paragraph.join('\n'))});paragraph=[];}};
  const flushList=()=>{if(list?.length)blocks.push({kind:'list',ordered:listOrdered,items:list});list=null;};
  for(const line of lines){
    const fence=line.match(FENCE);
    if(fence){
      if(code===null){flushParagraph();flushList();code=[];codeLang=fence[1].trim();}
      else{blocks.push({kind:'code',lang:codeLang,lines:code});code=null;}
      continue;
    }
    if(code!==null){code.push(line);continue;}
    if(!line.trim()){flushParagraph();flushList();continue;}
    const heading=line.match(HEADING);
    if(heading){flushParagraph();flushList();blocks.push({kind:'heading',level:heading[1].length,inlines:inlineTokens(heading[2])});continue;}
    const bullet=line.match(BULLET),ordered=line.match(ORDERED);
    if(bullet||ordered){
      flushParagraph();
      const wantOrdered=!!ordered;
      if(list&&listOrdered!==wantOrdered)flushList();
      list??=[];listOrdered=wantOrdered;
      list.push(inlineTokens((bullet?.[1]||ordered?.[1]||'').trim()));
      continue;
    }
    flushList();paragraph.push(line.trim());
  }
  if(code!==null)blocks.push({kind:'code',lang:codeLang,lines:code});
  flushParagraph();flushList();
  return blocks;
}
