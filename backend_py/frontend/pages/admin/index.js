import Link from 'next/link';

export default function AdminHome() {
    return ( <
        div className = "container" >
        <
        h1 > Admin Panel < /h1> <
        ul >
        <
        li > < Link href = "/admin/dashboard" > < a > Dashboard < /a></Link > < /li> <
        /ul> <
        /div>
    );
}