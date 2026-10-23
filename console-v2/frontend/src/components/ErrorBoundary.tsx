import {Component,type ErrorInfo,type ReactNode} from 'react';

type Props={children:ReactNode;section:string};
type State={error:Error|null};

export class SectionErrorBoundary extends Component<Props,State>{
  state:State={error:null};
  static getDerivedStateFromError(error:Error):State{return {error};}
  componentDidCatch(error:Error,info:ErrorInfo){console.error('工作台区块崩溃：'+this.props.section,error,info.componentStack);}
  render(){
    if(this.state.error)return <section className="section-crash" role="alert"><h2>这一小块暂时没有加载出来。</h2><p>其他页面仍可使用，也可以重试这一部分。</p><button className="button secondary" onClick={()=>this.setState({error:null})}>重试</button></section>;
    return this.props.children;
  }
}
