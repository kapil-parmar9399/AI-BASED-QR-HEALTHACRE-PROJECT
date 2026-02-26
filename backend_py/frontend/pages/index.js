import Link from 'next/link';

export default function Home() {
    return ( <
        div className = "container" >
        <
        h1 > Welcome to Swasthya < /h1> <
        p > Please < Link href = "/login" > < a > login < /a></Link > to
        continue. < /p> <
        /div>
    );
}